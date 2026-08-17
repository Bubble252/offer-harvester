# 迁移映射表

## 映射原则

本项目最终代码以自有实现为主。迁移分为四类：

- `Borrow idea`：只借鉴设计，不复用代码
- `Rewrite`：按本项目需求重写
- `Adapter`：通过适配器调用外部能力
- `Do not use`：不进入本项目

## 外部申请流程项目映射

| 原模块 | 原作用 | 保研项目映射 | 迁移策略 | 说明 |
|---|---|---|---|---|
| `/setup` | 构建求职 profile | 学生画像导入 | Borrow idea + Rewrite | 借鉴多入口、交叉校验、用户确认变更 |
| `documents/` | 存放 CV、LinkedIn、证书、申请记录 | `workspace/` | Rewrite | 改成 profiles、advisor_sources、targets、applications |
| `01-candidate-profile.md` | 候选人事实源 | `StudentProfile` | Rewrite | 字段改为 GPA、排名、科研、论文、竞赛、课程 |
| `04-job-evaluation.md` | 岗位匹配评分 | `AdvisorMatchService` | Borrow idea + Rewrite | 岗位要求改为导师方向和招生要求 |
| `/apply` | 申请材料生成 | `MaterialGenerationService` | Borrow idea + Rewrite | CV/Cover Letter 改为套磁邮件、PS、RP、PPT 大纲 |
| drafter-reviewer | 草稿和审稿分离 | `ReviewPipeline` | Borrow idea | 保留双阶段审查：生成者 + 事实/匹配 reviewer |
| grounding audit | 检查事实是否来自 profile | `EvidenceAudit` | Rewrite | 要求学生证据和导师来源双证据链 |
| `/interview` | 面试准备包 | `InterviewPrepService` | Borrow idea + Rewrite | 公司面试改为导师面谈、夏令营面试 |
| `/outcome` | 记录申请结果 | `ApplicationTracker` | Borrow idea + Rewrite | 状态词改为保研申请状态 |
| `/html-report` | 生成离线 dashboard | `ReportService` | Rewrite | 可重写一个中文保研申请看板 |
| `tools/verify_pdf.py` | PDF 页数和文本层检查 | `DocumentVerifyTool` | Rewrite if needed | 第一版不是核心，可后置 |
| `tools/security_guards.py` | 防止敏感文件泄露 | `SecurityGuard` | Rewrite | 按本项目 workspace/.env 规则重写 |
| job portal scrapers | 搜索岗位 | 无 | Do not use | 与保研导师资料采集不同 |
| CV LaTeX 模板 | 求职简历模板 | 无 | Do not use | 保研材料需独立模板 |
| Cover Letter 模板 | 求职动机信模板 | 无 | Do not use | 套磁邮件需要重新设计 |
| Claude Code commands | CLI 命令工作流 | 无 | Do not use | 第一版是 Web UI，不采用命令体系 |

## 外部演示文稿生成项目映射

| 原模块 | 原作用 | 保研项目映射 | 迁移策略 | 说明 |
|---|---|---|---|---|
| 原后端上传/生成服务 | FastAPI 上传/生成/下载 | `PresentationAdapter` | Adapter | 不复制原后端，只实现自有调用层 |
| `/api/upload` | 上传 PPTX/PDF 并创建任务 | `POST /api/ppt/tasks` | Borrow idea + Rewrite | 参数改为保研 PPT 类型、导师目标、材料 ID |
| `/wsapi/{task_id}` | 生成进度 | `WebSocket /api/tasks/{id}/ws` | Borrow idea + Rewrite | 进度系统自有实现 |
| `/api/download` | 下载 final.pptx | `GET /api/generated/{id}/download` | Borrow idea + Rewrite | 统一生成物下载接口 |
| `runs/` | 任务缓存目录 | `workspace/generated/` + `workspace/ppt_runs/` | Rewrite | 避免复用原路径结构 |
| `ModelManager` | 管理 LLM / vision / embedding | `LLMProvider` | Borrow idea or Adapter | 先用本项目统一模型配置 |
| `parse_pdf` | PDF 转 Markdown | `DocumentParser` | Adapter or Rewrite | 可调用，也可后续换轻量解析 |
| `Document.from_markdown_async` | 构建文档结构 | `MaterialDocument` | Adapter | 只在生成 PPT 时使用 |
| `Presentation.from_file` | 读取参考 PPT | `TemplateParser` | Adapter | 用于学习参考模板 |
| `SlideInducterAsync` | 归纳 PPT 版式 | `TemplateInductionAdapter` | Adapter | 依赖较重，先验证运行 |
| 原生成器入口 | 生成 PPTX | `PresentationGenerationAdapter` | Adapter | 核心集成点 |
| 原 Vue 前端 | 上传/生成/下载 UI | 本项目 Web UI | Do not use | 保研工作台重写 UI |
| 原强化学习目录 | 大纲/内容 RL 训练 | RL 后续增强 | Borrow idea | 不进入 MVP |

## 本项目自有模块映射

### Profile Service

来源参考：

- 外部申请流程项目的 profile setup

自有职责：

- 上传和解析中文简历、成绩单、科研项目材料
- 构建 `StudentProfile`
- 记录用户确认过的事实
- 标记不确定或冲突事实

### Advisor Source Service

来源参考：

- 外部申请流程项目的 URL/pasted text 双入口思想

自有职责：

- 接收导师主页 URL
- 尝试抓取正文
- 抓取失败时允许手动粘贴
- 保存 `AdvisorSource`
- 解析导师画像
- 保留来源证据

### Target Service

来源参考：

- 外部申请流程项目的 tracker

自有职责：

- 管理导师、实验室、硕士/直博项目
- 绑定导师资料来源
- 管理 deadline 和申请轮次

### Matching Service

来源参考：

- 外部申请流程项目的 fit evaluation

自有职责：

- 学生画像和导师方向匹配
- 输出 `strong_fit/reasonable_fit/weak_fit/unknown`
- 给出证据链
- 稳妥申请优先，不输出录取概率

### Material Generation Service

来源参考：

- 外部申请流程项目的 application workflow

自有职责：

- 中文套磁邮件
- 中文个人陈述大纲
- 中文研究计划大纲
- 中文科研项目介绍
- 面试 PPT 大纲
- reviewer 审查

### Interview Prep Service

来源参考：

- 外部申请流程项目的 interview prep

自有职责：

- 导师面谈问题
- 科研项目深挖问题
- 夏令营面试准备
- 英语口语问题作为扩展
- 已提交材料一致性检查

### Presentation Adapter

来源参考：

- 外部演示文稿生成项目的后端生成链路

自有职责：

- 接收本项目生成的 PPT 大纲和材料
- 调用 presentation_engine 或降级为中间文件
- 返回任务状态和 PPTX 下载路径
- 不复制外部演示文稿项目源码

### Report Service

来源参考：

- 外部申请流程项目的 HTML report

自有职责：

- 生成中文保研申请看板
- 展示目标池、套磁状态、材料状态、面试状态
- 离线 HTML 报告

### Security Guard

来源参考：

- 外部申请流程项目的 security guard 思路

自有职责：

- 检查 `.env` 是否泄露
- 检查 `workspace/` 是否误提交
- 检查 API key 模式
- 检查是否复制外部项目整目录

## API 映射草案

| API | 作用 | 来源参考 |
|---|---|---|
| `POST /api/profile/upload` | 上传学生资料 | `/setup` |
| `GET /api/profile` | 获取学生画像 | `/setup` |
| `POST /api/advisor-sources` | 添加导师 URL 或文本 | `/apply` Step 0 |
| `GET /api/advisor-sources` | 获取导师来源列表 | 自有 |
| `POST /api/targets` | 创建导师/项目目标 | job tracker |
| `GET /api/targets` | 目标池列表 | job tracker |
| `POST /api/targets/{id}/match` | 匹配分析 | fit evaluation |
| `POST /api/targets/{id}/materials/contact-email` | 生成套磁邮件 | `/apply` |
| `POST /api/targets/{id}/materials/interview` | 生成面试题 | `/interview` |
| `POST /api/targets/{id}/ppt` | 生成面试展示 PPT | presentation_engine |
| `GET /api/applications` | 申请状态列表 | `/outcome` |
| `PATCH /api/applications/{id}` | 更新申请状态 | `/outcome` |
| `GET /api/report` | 下载 HTML 看板 | `/html-report` |

## 第一版优先级

### P0：必须实现

- Web UI
- 学生资料上传
- 导师 URL 抓取 + 手动粘贴兜底
- 导师字段结构化
- 匹配分析
- 中文套磁邮件
- 中文面试问题
- 申请状态跟踪

### P1：尽量实现

- 中文个人陈述大纲
- 中文研究计划大纲
- PPT 大纲生成
- presentation_engine 适配器初版
- HTML 看板

### P2：后续实现

- 演示文稿生成能力完整直接生成
- 导师论文批量分析
- 英文材料
- 强化学习优化
- 多用户和部署版

## 不进入最终框架的内容

- 外部申请流程项目整目录
- 外部演示文稿生成项目整目录
- Claude Code 命令体系
- 求职网站爬虫
- 求职 LaTeX 模板
- 外部演示文稿项目原 Vue 前端
- 强化学习训练输出模型
- 真实学生资料
- 真实 API key
