# 参考项目补充借鉴点审查

本文档记录对 `ai-job-search-master` 和 `PPTAgent` 的二次审查结果，重点关注当前规划中尚未明确展开、但值得纳入未来路线的功能。

## ai-job-search-master 可继续借鉴

### 申请生命周期归档

`ai-job-search-master` 的 `/outcome` 不只是改状态，而是把一次申请的材料、岗位原文、结果和复盘写入 per-application archive。

本项目可迁移为：

```text
workspace/application_archives/
└── <school>_<advisor_or_program>/
    ├── target_snapshot.json
    ├── submitted_materials/
    ├── communications/
    ├── outcome.md
    └── lessons.md
```

用途：

- 保留“当时实际提交/发送的版本”
- 记录导师回复、面试阶段、录取/拒绝/无回复结果
- 后续校准匹配评分、申请准备度评分和 Agentic RL reward

### Follow-up 与 Thank-you Note

参考 `/outcome followup`：

- 套磁后若目标长期无回复，可以生成短 follow-up 草稿
- 面试后可以生成 thank-you note 草稿
- 默认只生成草稿，不自动发送
- 每个目标最多跟进有限次数，避免过度打扰
- 所有 substantive claim 必须来自已经发送过的材料或已确认 profile

### 邮箱状态同步

参考 `/gmail-sync`：

- 只读邮箱，不自动发信
- 识别导师回复、夏令营通知、面试邀请、补材料要求、拒信、录取/拟录取提醒
- 每条候选更新必须引用源邮件
- 用户批准后才写入 tracker / archive
- 冲突、不确定、无法匹配的邮件只提示人工复核

### 外部看板单向同步

参考 `/notion-sync`：

- 本地 workspace 仍是唯一系统事实源
- Notion / 飞书 / Google Sheets 只是展示层
- 只同步目标状态、分数、deadline、下一步行动和本地文件名
- 不同步真实申请材料正文、成绩单、联系方式等敏感内容
- 页面正文 write-once，后续只更新属性，避免覆盖用户手写备注

### 批量粗排与深度分析分层

参考 `/rank`：

- 批量导师/项目粗筛只做轻量打分
- 深度分析仍由目标详情页触发
- 粗排结果保存 strengths、gaps、deadline、hard gates
- 过期、硬门槛不满足、证据不足的目标单独列出

### Profile Expand 能力补全

参考 `/expand`：

- 从本地资料和公开链接中发现候选能力
- 支持 GitHub、Google Scholar、ORCID、个人主页、项目主页、课程/证书页面
- 所有新增能力先进入候选区，不直接写入正式 profile
- 用户确认后才写入 profile
- 每个能力都记录来源和推断方式

### Gap / Upskill 改进计划

参考 `/upskill`：

- 从目标导师/项目要求和当前学生画像做差距分析
- 输出 gap heatmap
- 给出材料补强、论文阅读、项目讲解、英语问答、证明材料准备等行动计划
- 后续可和申请准备度评分联动

### 模板注册与激活

参考 `/add-template`：

- 支持 PS、研究计划、套磁邮件、PPT 等模板注册
- 每个模板有 manifest，记录类型、适用场景、变量、风格规则、限制和验证方式
- 激活模板通过 managed block 或配置引用，不改写原始协议
- 模板必须通过样例渲染或格式检查后才能启用
- 当前已补充用户模板上传、Markdown/纯文本在线编辑、版本 diff 和 draft/validated/active/disabled/archived 生命周期
- 用户模板只保存到本地 `workspace/templates/`，不进入 Git；PPTX 参考模板只做上传和元数据管理

### 来源连接器生成器

参考 `/add-portal`：

- 为学校官网、学院通知页、导师主页、招生系统生成 source connector
- 每个 connector 记录 URL 模式、字段映射、访问限制、robots/ToS 提醒、测试查询和公开测试 URL
- live test 通过后才标记为可注册；manifest 合法不等于 live test 已通过
- 生成器输出留在用户 workspace 或 fork，不作为主项目默认内置爬虫
- 当前已支持默认 7 天到期检测、API 手动刷新和命令行刷新；不启动常驻后台调度器

### PDF / 文档可读性验证

参考 `/apply` 的 PDF 编译和 ATS text layer 检查；当前已提供轻量 PDF 可读性检查器：

- 检查 PDF 结构、页数、文本层、潜在空白页和关键字段可抽取性
- 无文本层的扫描件标记 `needs_ocr`，暂不引入 PaddleOCR
- 检查报告保存到本地 workspace，并可回写材料质量报告
- 该能力仍后置于 PDF 导出，不影响当前 Markdown/PPTX MVP

## PPTAgent 可继续借鉴

### 参考 PPT 预检

PPTAgent 的 best practice 明确了参考 PPT 的可解析边界。可规划：

- 检查 nested group、freeform、音视频、复杂形状
- 记录跳过页面和原因
- 检查每页元素数量、文本溢出策略、功能页是否齐全
- 对复杂参考模板给出降级提示

### 生成参数

可暴露为保研 PPT 参数：

- `num_slides`：目标页数
- `length_factor`：详略程度
- `sim_bound`：参考内容召回相似度
- `hide_small_pic_ratio`：小图处理阈值
- `keep_in_background`：小图是否保留为背景元素
- `error_exit`：单页失败是否中断整份生成

### Slide Schema 抽取

PPTAgent 会把 slide 抽成结构化 schema。本项目可用于：

- 识别标题、正文、图片、logo、日期、页脚等元素
- 约束生成内容不超出模板槽位
- 支持单页编辑和 PPT 质量审计

### 内容组织器

PPTAgent 的 content organizer 会同时输出 paragraph form 和 bullet form。保研场景可用于：

- 把科研项目整理成讲稿版和 PPT bullet 版
- 把论文/项目经历整理成“可讲清楚”的面试展示内容
- 控制每页文字密度

### 功能页规则

PPTAgent 区分 Opening、TOC、Section Header、Ending。保研场景可以扩展为：

- 3 分钟面试：无 TOC，直接进入教育背景和项目
- 5 分钟面试：封面、背景、项目、匹配、计划
- 10 分钟面试：可加入 TOC、section header、研究计划和 Q&A 备用页

### 单页 PPT Copilot

PPTAgent 的 copilot/schema/coder 思路适合后续交互编辑：

- 用户选择某一页
- 输入“减少文字”“突出科研贡献”“换成流程图结构”
- 系统只改该页，并保留其他页不动
- 修改前后记录版本和质量检查结果

### PPTEval 三维评分

PPTAgent 的 PPTEval 分为：

- Content：内容是否准确、相关、有证据
- Design：视觉是否一致、可读、层级清晰
- Coherence：逻辑是否顺畅，页面之间是否连贯

本项目可把它作为申请准备度评分中的 PPT 子评分。

### 外部 Runtime 预检

如果后续接真实 PPTAgent，需要在运行前检查：

- LibreOffice
- Chrome
- poppler-utils
- NodeJS
- Python 版本
- 端口占用
- LLM / Vision / Embedding 模型配置
- GPU / 内存条件

不满足条件时应 fallback 到 `LocalPptxAdapter`，并记录原因。

## 已写入 03 的后续阶段

- 阶段 15：申请生命周期、跟进与外部同步
- 阶段 16：批量目标策略、画像扩展与模板/连接器治理
- 阶段 17：PPTAgent 高级生成、编辑与评估能力

这些阶段都保持当前原则：不复制参考项目源码，不把外部服务变成 MVP 必需依赖，所有事实写入必须经过证据和用户确认。
