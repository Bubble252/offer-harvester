# 现有项目审计

## 审计目标

本阶段审计两个现有项目：

- `/home/bubble/agent/ai-job-search-master`
- `/home/bubble/agent/居丽叶简历项目2：PPTAgent`

审计目的不是搬运源码，而是判断：

- 哪些流程设计值得借鉴
- 哪些底层能力可以重写或包装成自有模块
- 哪些代码不适合进入最终项目
- 哪些集成点需要通过适配器调用

最终代码框架不允许出现这两个项目的整目录复制体。

## ai-job-search-master 审计

### 项目定位

`ai-job-search-master` 是一个面向求职申请的 Claude Code 工作流框架。它把求职流程拆成：

```text
个人画像
-> 岗位搜索
-> 匹配评估
-> CV / Cover Letter 定制
-> reviewer 审查
-> 面试准备
-> 结果记录
-> HTML 报告
```

对本项目最有价值的是流程思想，而不是求职领域的具体模板。

### 关键模块

#### `/setup`

作用：

- 从 `documents/` 读取用户资料
- 支持多入口：资料夹、单个 CV、访谈模式
- 交叉校验资料一致性
- 先展示变更集，再由用户确认写入
- 将资料沉淀为结构化 profile

可迁移思想：

- 保研版可以设计为“学生资料导入”
- 支持上传简历、成绩单、科研项目、论文、获奖证明
- 对同一事实进行交叉校验，例如 GPA、排名、项目时间、论文状态
- 不直接覆盖用户资料，先展示冲突和新增项

不直接复用原因：

- 原文件结构绑定 `.claude/skills/job-application-assistant/`
- 字段围绕求职经历，不适合保研硕博申请
- 命令语义强依赖 Claude Code

#### `/apply`

作用：

- 解析岗位 URL 或粘贴文本
- 对岗位和候选人做匹配评分
- 用户确认后生成 CV 和 Cover Letter
- 使用 drafter-reviewer 双角色审查
- 做事实 grounding audit
- 编译并检查 PDF

可迁移思想：

- 保研版对应“导师/项目申请材料生成”
- 岗位文本替换为导师主页、实验室主页、招生通知、论文方向
- CV/Cover Letter 替换为中文套磁邮件、个人陈述、研究计划、面试 PPT 大纲
- reviewer 审查可用于检查事实一致性、导师方向匹配和过度包装

不直接复用原因：

- 原流程强绑定求职岗位和 LaTeX 简历
- PDF 编译检查对本项目不是第一优先级
- cover letter 模板和 CV 模板不能直接用于保研材料

#### `/interview`

作用：

- 基于已追踪申请准备面试包
- 读取已提交材料和过往反馈
- 生成可能问题、STAR 映射、tough questions、反问问题
- 强调材料一致性：面试说法不能超出已提交材料

可迁移思想：

- 保研版可以生成导师面谈/夏令营面试准备包
- 重点问题来自导师方向、学生科研经历、材料短板和已提交内容
- 面试准备必须和套磁邮件、个人陈述、PPT 内容一致
- 可以输出中文模拟面试题和回答要点

不直接复用原因：

- 原面试框架面向公司招聘
- STAR 行为面试结构在保研中只适合作为辅助，不是核心

#### `/html-report`

作用：

- 从 tracker CSV 和申请归档生成离线 HTML dashboard
- 支持状态统计、漏斗统计、表格筛选
- 完全离线，无外部依赖

可迁移思想：

- 保研版可以生成申请看板
- 状态从 `drafted/applied/interview/...` 替换为 `researching/contacted/replied/submitted/interview/accepted/rejected`
- 图表可展示导师池、套磁回复率、材料完成度、面试进度

可重写为本项目自有模块：

- HTML 报告生成器
- 状态归一化
- 表格筛选
- 简单 SVG 图表

#### 工具脚本

发现的可借鉴工具：

- `tools/verify_pdf.py`
- `tools/security_guards.py`
- `tools/lint_skills.py`
- `tools/robots_check.py`
- `tests/test_*`

可借鉴点：

- PDF 文本层验证思路
- 隐私数据 `.gitignore` 保护
- API key 和敏感文件防泄露
- CI 中安全规则显式化
- 测试覆盖 workflow 约束

不建议直接复制：

- 原脚本中的 allowlist 和路径都绑定求职项目
- 安全规则应按本项目的 `workspace/`、导师资料和 LLM 配置重新编写

### ai-job-search 结论

建议定位：

```text
流程设计参考 + 少量底层工具重写依据
```

不建议：

```text
直接 fork / 直接复制目录 / 直接复用求职命令体系
```

## PPTAgent 审计

### 项目定位

PPTAgent 是一个根据文档和参考 PPT 自动生成演示文稿的系统。它包含：

- PDF 解析
- 参考 PPT 解析
- 模板版式归纳
- 幻灯片内容组织
- PPTX 生成
- FastAPI 上传、进度、下载服务
- Vue 前端

对本项目最有价值的是“参考模板驱动的 PPT 生成能力”和“异步任务进度链路”。

### 后端 API 审计

关键文件：

```text
pptagent_ui/backend.py
```

已有接口：

- `POST /api/upload`
- `GET /api/download`
- `POST /api/feedback`
- `WebSocket /wsapi/{task_id}`

核心流程：

```text
上传参考 PPTX 和 PDF
-> 保存到 runs 目录
-> 等待 WebSocket 连接
-> 解析参考 PPT
-> PPT 转图片
-> 图片 caption
-> 解析 PDF 为 Markdown
-> Document.from_markdown_async
-> SlideInducterAsync 归纳模板
-> PPTAgentAsync.generate_pres
-> 保存 final.pptx
-> 下载
```

可借鉴或适配：

- 任务 ID 设计
- 文件 hash 缓存
- WebSocket 进度上报
- 生成结果下载
- runs 目录分层
- 参考 PPT 模板学习

需要重写或包装：

- 原接口参数面向通用 PPT 生成，不懂保研业务
- 原 `RUNS_DIR` 使用全局路径和全局状态
- 原 `progress_store` 和 `active_connections` 是内存状态，不适合长期任务恢复
- 原前端交互过于简单，不适合保研工作台

### 可用底层能力

关键模块：

- `pptagent.model_utils.ModelManager`
- `pptagent.model_utils.parse_pdf`
- `pptagent.document.Document`
- `pptagent.presentation.Presentation`
- `pptagent.induct.SlideInducterAsync`
- `pptagent.pptgen.PPTAgentAsync`
- `pptagent.utils.ppt_to_images_async`

建议集成方式：

```text
本项目生成保研 PPT 中间材料
-> PPTAdapter 接收 markdown/json + 可选参考 PPTX
-> 调用 PPTAgent 能力生成 PPTX
-> 返回生成状态和下载路径
```

不建议：

- 复制 `pptagent/` 整个目录进入本项目
- 复制 `pptagent_ui/` 前端
- 直接复用原 `backend.py` 作为本项目后端

### 强化学习版本审计

目录：

```text
PPTAgentv2.0带强化学习版/backend/
```

包含两个训练模块：

- `outline/train_trl.py`
- `content/train_trl.py`

作用：

- 用 GRPO/GSPO 训练大纲生成模型
- 用规则奖励和 DeepSeek Judge 评价输出
- 训练主题到 Markdown 大纲
- 训练大纲到完整内容

当前限制：

- 数据量较小
- 未接入主 PPTAgent Web 链路
- 不训练 PPT 排版
- 不适合作为 MVP 主依赖

建议定位：

```text
MVP 后的结构化内容生成优化参考
```

适合未来训练：

- 导师匹配分析结构
- 稳妥型套磁邮件结构
- 面试 PPT 大纲
- 研究计划大纲

不适合第一版：

- 端到端保研 Agent
- 自动录取概率
- PPT 视觉排版模型

## 风险与注意事项

### 许可证和来源

- `ai-job-search-master` 需要确认 LICENSE 后再决定是否复用任何底层代码
- PPTAgent 为 MIT，但仍不建议复制整目录
- 如果复用单个函数，需要在文件头或 NOTICE 记录来源

### 隐私风险

本项目会处理：

- 简历
- 成绩单
- 推荐材料
- 套磁邮件
- 导师联系记录

必须保证：

- `workspace/` 不进入 Git
- 示例数据匿名
- 真实用户资料不进入测试和文档

### 技术风险

- PPTAgent 依赖较重，可能需要单独环境验证
- PDF/PPT 解析依赖外部工具和模型
- 导师 URL 抓取可能遇到反爬、乱码、PDF 通知等问题
- Web UI 第一版需要避免功能过多导致延期

## 总体结论

建议采用：

```text
自有保研业务代码
+ ai-job-search 流程借鉴
+ PPTAgent 适配器调用
+ 底层工具按需重写
+ 强化学习后置
```

不采用：

```text
复制 ai-job-search-master
复制 PPTAgent
直接 fork 改名
第一版接入强化学习
第一版做大规模导师爬虫
```
