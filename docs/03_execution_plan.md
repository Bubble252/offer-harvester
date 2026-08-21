# 执行计划

## 当前目标

当前阶段目标是先完成产品和技术规划，不直接进入大规模代码改造。

原因：

- 两个项目体量都较大，需要先确认可复用边界
- 保研/升学场景和求职场景相似但不完全相同
- 演示文稿参考项目的强化学习版本尚未接入主生成链路
- 需要先定义 MVP，避免功能扩散
- 第一版以保研硕博申请的稳妥申请为主，需要真实导师信息作为输入和证据来源

## 阶段 0：需求确认与项目边界

- [x] 明确项目方向：保研硕博申请全流程工作台
- [x] 明确两个现有项目的组合价值
- [x] 新建项目目录
- [x] 创建三份初始规划文档
- [x] 确认第一版主要服务保研中的硕博申请
- [x] 确认第一版策略以稳妥申请为主
- [x] 确认需要真实导师信息作为目标资料来源
- [x] 确认真实导师信息第一版采用“URL 抓取 + 手动粘贴兜底”
- [x] 确认第一版材料语言以中文为主
- [x] 确认第一版需要 Web UI，而不是本地命令行/脚本 Demo
- [x] 确认 MVP 可以先不接入强化学习
- [x] 确认后续需要规划强化学习接入路线
- [x] 确认不直接改造外部申请流程项目，以借鉴和局部底层复用为主
- [x] 确认演示文稿生成能力优先通过适配层直接调用，业务代码按本项目重写
- [x] 确认最终代码框架不允许出现借鉴项目的复制体
- [x] 确认文档中可以明确记录参考项目和参考部位
- [x] 确认代码注释需要符合规范
- [x] 确认保留原项目许可证说明和第三方引用说明，并在 `NOTICE` 中记录边界
- [x] 确认每个逻辑开发步骤都需要有合规、详细且可验证的 Git commit
- [x] 确认 Git commit、分支和推送规范已记录到开源文档

## 阶段 1：现有项目梳理

目标：搞清楚哪些代码可以直接复用，哪些只适合作为设计参考。

- [x] 阅读外部申请流程项目的命令工作流
- [x] 识别外部申请流程项目中可直接复用的底层模块
- [x] 识别外部申请流程项目中只适合借鉴的流程模块
- [x] 梳理 `/setup` 对应的学生画像迁移方式
- [x] 梳理 `/apply` 对应的申请材料生成迁移方式
- [x] 梳理 `/interview` 对应的复试/导师面试迁移方式
- [x] 梳理 `/html-report` 对应的申请看板迁移方式
- [x] 阅读演示文稿参考项目的后端生成链路
- [x] 识别演示文稿参考项目中可直接调用的后端入口
- [x] 识别演示文稿参考项目中可直接复用的底层函数
- [x] 阅读演示文稿参考项目的前端上传/进度/下载链路
- [ ] 确认演示文稿生成能力是否能用测试文件跑通
- [x] 确认真实导师信息的采集方式：URL 抓取 + 手动粘贴兜底
- [x] 初步细化真实导师信息字段结构
- [x] 输出一份模块迁移清单

交付物：

- `docs/04_existing_projects_audit.md`
- `docs/05_migration_mapping.md`

## 阶段 2：MVP 功能定义

目标：把产品收敛为一个可演示闭环。

规格交付：

- [x] 完成 MVP 功能规格文档
- [x] 完成 Web UI 用户流程文档
- [x] 完成数据 Schema 初稿
- [x] 完成强化学习后续接入计划

建议 MVP：

- [ ] 学生资料上传
- [ ] 学生画像提取
- [ ] 目标导师/项目创建
- [ ] 真实导师信息录入
- [ ] 导师主页/实验室主页/招生通知解析
- [ ] 导师资料来源记录
- [ ] 匹配度分析
- [ ] 套磁邮件生成
- [ ] 定制申请摘要生成
- [ ] 模拟面试题生成
- [ ] 面试展示 PPT 生成
- [ ] 申请状态记录

暂缓功能：

- [ ] 大规模自动爬取院校和导师主页
- [ ] 多用户账号系统
- [ ] 云端部署
- [ ] 自动发送邮件
- [ ] 强化学习模型在线推理
- [ ] 复杂数据库

交付物：

- `docs/06_mvp_spec.md`
- `docs/07_user_flow.md`
- `docs/08_data_schema.md`
- `docs/09_rl_integration_plan.md`
- `docs/10_open_source_readiness.md`

## 阶段 3：项目脚手架

目标：建立新项目的基本代码结构。

建议结构：

```text
grad-apply-workflow/
├── docs/
├── app/
│   ├── backend/
│   └── frontend/
├── workspace/
│   ├── profiles/
│   ├── advisor_sources/
│   ├── targets/
│   ├── applications/
│   ├── generated/
│   └── reports/
└── integrations/
    ├── workflow_engine/
    └── presentation_engine/
```

注意：`integrations/` 不是外部项目源码副本目录，只能放本项目自有的适配器、接口定义、调用包装和降级逻辑。调研时产生的源码摘录或项目复制只能作为中间产物，不进入最终代码框架。

任务：

- [x] 创建后端目录
- [x] 创建前端目录
- [x] 创建 workspace 目录
- [x] 创建 integrations 适配器目录，但不复制外部项目源码
- [x] 建立代码注释规范检查清单
- [x] 定义基础配置文件
- [x] 定义数据模型
- [x] 定义 API 路由草案
- [x] 准备样例学生资料
- [x] 准备真实导师/项目样例资料
- [x] 准备导师来源记录样例

交付物：

- 基础项目结构
- 示例数据
- API 草案

## 阶段 3.5：开源项目骨架

目标：把项目整理成标准 GitHub 开源项目，而不是只有业务代码。

任务：

- [x] 创建 `README.md`
- [x] 创建 `LICENSE`（MIT）
- [x] 创建 `.gitignore`
- [x] 创建 `.env.example`
- [x] 创建 `CONTRIBUTING.md`
- [x] 创建 `SECURITY.md`
- [x] 创建 `CHANGELOG.md`
- [x] 创建 `workspace.example/`
- [x] 创建 `tests/`
- [x] 创建 `.github/workflows/ci.yml`
- [x] 明确外部项目借鉴与集成边界
- [x] 创建 `NOTICE`，记录参考项目、许可证核对要求和未来复用约束
- [x] 创建基础 CI，运行后端和适配器测试
- [x] 明确用户隐私数据不进入 Git

交付物：

- 标准 GitHub 项目根目录
- 匿名示例数据
- 基础 CI
- 开源安全与贡献说明

## 阶段 4：后端 MVP

目标：先不追求复杂 UI，跑通核心逻辑。

后端模块：

- [x] Profile Service：学生画像管理
- [x] Advisor Source Service：真实导师资料来源管理
- [x] Target Service：目标导师/项目管理
- [x] Matching Service：匹配分析
- [x] Material Service：材料生成与基础质量检查
- [x] Interview Service：面试准备
- [x] Tracker Service：申请状态跟踪
- [x] Report Service：本地进度报告生成
- [x] Presentation Adapter：Markdown 大纲降级适配

API 草案：

```text
POST /api/profile/upload
GET  /api/profile
POST /api/advisor-sources
GET  /api/advisor-sources
POST /api/targets
GET  /api/targets
GET  /api/targets/{id}
POST /api/targets/{id}/match
POST /api/targets/{id}/materials/email
POST /api/targets/{id}/materials/interview
POST /api/targets/{id}/ppt
GET  /api/applications
PATCH /api/applications/{id}
GET  /api/report
```

交付物：

- 可运行 FastAPI 后端
- 本地 JSON 文件存储
- 至少一个完整 Demo 案例

## 阶段 5：前端 MVP

目标：让用户能在浏览器里走完整流程。

页面：

- [x] 首页/工作台
- [x] 学生资料页
- [x] 目标池页面
- [x] 目标详情与状态更新
- [x] 匹配分析与材料预览
- [x] 材料生成、质量检查与 Markdown 下载
- [ ] PPT 生成进度页（等待阶段 6 的异步 PPTX 任务）
- [x] 面试准备入口
- [x] 申请看板与进度报告

交付物：

- 可操作 Web Demo
- 支持文件上传
- 支持长任务进度
- 支持下载 Markdown/PPTX

## 阶段 6：演示文稿生成集成

目标：让升学场景真的生成可编辑 PPT。

任务：

- [x] 定义升学 PPT 的中间 Markdown 格式
- [x] 设计 5 页自我介绍 PPT 模板结构
- [ ] 设计科研项目展示 PPT 模板结构（后续扩展）
- [x] 验证本地 PPTX 生成依赖可运行
- [x] 识别可选外部演示文稿引擎的后端入口与独立运行时边界
- [x] 编写 `presentation_engine` 自有适配器
- [ ] 支持上传参考 PPT 模板（后续扩展）
- [x] 支持生成并下载可编辑 PPTX
- [x] 记录生成任务状态和失败原因

推荐先支持一种 PPT：

```text
5 页自我介绍 PPT
1. 封面
2. 教育背景与能力概览
3. 代表科研/项目经历
4. 与目标导师方向的匹配
5. 未来研究计划与结束页
```

## 阶段 7：导师信息采集与目标创建闭环

目标：把“真实导师信息 -> 导师画像 -> 申请目标 -> 后续材料生成”的第一条产品链路做扎实。

为什么这一阶段优先：

- 第一版以保研硕博申请为主，导师信息质量决定后续匹配和材料生成质量
- URL 抓取不稳定，必须把手动粘贴兜底做成正式流程，而不是异常处理
- 用户需要从导师资料自然进入申请目标，否则工作流会断在资料录入
- 后续质量控制、PPT 生成和材料生成都依赖清晰的导师证据来源

任务：

- [x] 新建导师信息采集页
- [x] 支持输入导师主页、实验室主页、招生通知和论文主页 URL
- [x] 支持手动粘贴导师介绍、招生说明和实验室介绍正文
- [x] 记录来源类型、来源链接、抓取状态、粘贴时间和可信度
- [x] 抓取失败时保留失败原因，并引导用户粘贴正文
- [x] 细化导师字段：姓名、学校、学院、职称、实验室、研究方向、招生类型、邮箱、主页链接
- [x] 细化导师字段：代表论文、项目经历、学生偏好、招生要求、近期关注点、风险提示
- [x] 每个导师结论都绑定来源证据，避免无来源推断
- [x] 支持从导师画像一键创建申请目标
- [x] 创建目标时自动带入导师摘要、研究方向、来源列表和申请建议
- [x] 支持目标优先级、申请轮次、截止日期、联系状态和下一步行动
- [x] 前端打通“保存导师画像 -> 创建申请目标 -> 进入目标详情”
- [x] 后端补充对应 API、数据校验和错误返回
- [x] 增加导师来源失败兜底、目标创建和证据绑定测试
- [x] 规划 GPT-5.5 / OpenAI-compatible API 作为 Agent 增强解析能力
- [x] 接入本地环境变量读取，不把 API key 写入代码、文档或 commit
- [x] 验证真实 GPT-5.5 API 能增强导师字段解析
  - 2026-08-17：已确认 `cc-switch` 当前 Codex provider 使用 `OPENAI_BASE_URL=https://www.aikeys.one`、`OPENAI_WIRE_API=responses`、`OPENAI_MODEL=gpt-5.5`
  - 2026-08-17：已用导师样例完成真实调用，LLM 增强结果能合并研究方向和招生要求；失败时仍保留规则解析回退
- [x] 增加导师画像人工编辑保存接口
- [ ] 增加真实网页抓取的端到端样例验证
- [ ] 按 `feat/advisor-intake` 分支和 `feat(advisor): 打通导师信息采集与目标创建` commit 规范提交

验收标准：

- 用户可以不依赖自动抓取，仅靠手动粘贴完成导师信息录入
- URL 抓取成功和失败两种路径都能保存 AdvisorSource
- 用户可以从导师资料一键创建 ProgramTarget
- 目标详情页能看到导师摘要、来源证据和下一步操作
- 后续匹配分析、邮件、面试问题和 PPT 大纲能使用该目标
- 测试覆盖正常路径、抓取失败兜底和缺少来源时的校验

交付物：

- 导师信息采集 Web 页面
- 导师画像编辑区
- 申请目标创建入口
- 导师来源与目标绑定 API
- 相关测试和文档更新

## 阶段 8：质量控制

目标：让材料更可靠，而不是只生成得像。

当前判断：

- 项目已经具备基础材料质量检查能力，但还停留在规则函数层面
- 下一步应把质量控制升级为独立的 reviewer / auditor 流程
- 质量控制必须服务保研申请的稳妥性，不做录取概率预测
- 每个高风险结论都应能追溯到学生资料、导师来源或用户确认记录
- 套磁邮件链路已接入字段级用户确认：未确认字段可用于草稿但会提示，已否认字段禁止继续使用

任务：

- [x] 将现有 `audit_material` 拆成独立质量检查模块
- [x] 事实一致性检查：材料中出现的成绩、排名、论文、项目、奖项必须来自学生画像或用户确认
- [x] 导师来源引用检查：导师方向、招生要求、代表论文、实验室信息必须绑定来源
- [x] 导师方向匹配检查：材料不能只泛泛说“感兴趣”，需要指出具体匹配点和证据
- [x] 材料模板化检查：识别过度通用、可替换导师姓名后仍成立的文本
- [x] 过度包装检查：禁止“保证录取”“稳上”“一定适合”等不稳妥表达
- [x] PPT 页数和可读性检查：控制页数、每页文字量、标题长度和讲述重点
- [x] 面试可解释性检查：材料中的每个项目表述都应能被学生口头解释
- [x] 增加质量检查测试：虚构论文、缺少导师证据、过度承诺、导师方向不匹配、材料和 profile 冲突
- [x] 在前端展示质量报告，而不只返回后端 JSON

输出：

```text
材料质量报告
风险项
建议修改点
证据引用
```

建议 commit：

```bash
git checkout -b feat/quality-review-pipeline
pytest -q
git add app/backend tests docs/03_execution_plan.md
git commit -m "feat(quality): add evidence-based material review pipeline"
git push -u origin feat/quality-review-pipeline
```

## 阶段 8.5：Agent 工作流深化

目标：把项目从“服务函数 + Prompt”提升为可审计、可恢复、可评估的保研申请 Agent 工作流。

为什么需要这一阶段：

- `ai-job-search-master` 的核心价值在于命令协议、技能文件、验证清单和 drafter-reviewer 分离，而不只是代码
- 当前项目后端已经能跑通 MVP，但 Agent 层仍偏薄，生成、审查、证据审计和用户确认没有形成统一协议
- 保研场景高风险点是事实夸大、导师方向误读和材料不可解释，需要 reviewer/auditor 作为一等模块

### 已有代码能力和待转化 Skill 的边界

当前项目已经有一批可运行代码，它们不等于 skill，但可以作为 skill 的底层工具或业务服务。

### 已确认决策与架构取舍

- [x] Agent 工作流第一优先级确定为“套磁邮件 drafter-reviewer-auditor”
- [x] 用户原始资料需要落盘，不能只保留结构化 profile
- [x] 用户编辑前后版本需要记录，用于审计、回滚和后续偏好数据积累
- [x] 马上补 `pyproject.toml`、ruff、更严格 CI 和 security guards
- [x] 第一阶段只做 portable skill 主目录，不做 `.codex/skills/` 或 `.claude/commands/` 薄指针

架构取舍：

- 保留 `services.py` 中已有的稳定业务能力，但逐步把它从“大杂烩服务文件”拆成更清晰的模块
- 不把 skill 写成业务代码替代品；skill 是 Agent 协议，业务代码仍在 `app/backend/`
- 不把 drafter、reviewer、auditor 都塞进 `make_contact_email`；应新增 Agent 层编排，调用现有生成函数作为 fallback
- `generated/` 继续保存最终生成材料；不把草稿、审稿意见、用户编辑版本混在同一层
- `quality_reports/` 继续保存质量检查报告；不承担完整版本历史职责
- 新增版本记录目录，用于保存 draft、reviewed、user_edited、final 等材料版本
- `workspace/user_documents/` 保存原始资料；`profiles/` 保存用户确认后的结构化画像；二者不能混用
- `integrations/` 只放外部能力适配器，不放 Agent 业务流程
- `app/backend/agents/` 负责 drafter-reviewer-auditor 编排、AgentRun 记录和事件记录
- `app/backend/services/` 后续应拆成 profile/advisor/matching/material/report 等模块，避免继续膨胀

已有代码能力：

- [x] `StudentProfile`、`AdvisorSource`、`AdvisorProfile`、`Target`、`MatchReport`、`GeneratedMaterial`、`ApplicationRecord` 等核心数据模型
- [x] `Workspace` 本地 JSON 存储，已覆盖 profiles、advisor_sources、advisors、targets、matches、generated、quality_reports、applications、presentation_tasks、reports
- [x] `build_profile_from_text`：规则式学生画像抽取
- [x] `create_advisor_source`：导师 URL 抓取、手动粘贴兜底、来源 hash 和失败原因记录
- [x] `validate_public_url`：基础 URL 安全校验，已阻止 localhost 和显式内网 IP
- [x] `parse_advisor_profile`：规则式导师画像抽取
- [x] `extract_advisor_profile_with_llm`：OpenAI-compatible LLM 增强导师字段抽取
- [x] `merge_advisor_profile_with_llm`：只接收带 evidence 和 confidence 的 LLM 字段
- [x] `make_match`：基础导师匹配分析
- [x] `make_contact_email`：中文套磁邮件草稿生成
- [x] `make_interview_questions`：中文面试问题生成
- [x] `make_ppt_outline`：5 分钟面试展示 PPT 大纲生成
- [x] `audit_material`：基础材料质量检查
- [x] `LocalPptxAdapter`：本地可编辑 PPTX 生成兜底
- [x] FastAPI 路由已打通资料上传、导师来源、导师画像编辑、目标创建、匹配、材料、PPT、申请状态、报告
- [x] 前端已能走主要 MVP 流程
- [x] 测试已覆盖基础 MVP 流、导师来源失败兜底、LLM evidence merge、PPTX 生成和 secret 检查

需要转化成 skill / Agent 协议的内容：

- [ ] `student-profile-intake`：把现有 `build_profile_from_text` 升级为“资料读取 -> 冲突检查 -> 用户确认 -> 结构化画像”的协议
- [ ] `advisor-intake`：把现有 `create_advisor_source` + `parse_advisor_profile` 升级为“来源采集 -> 身份消歧 -> 字段证据绑定 -> 人工复核”的协议
- [ ] `advisor-match-review`：把现有 `make_match` 升级为多维度匹配评估协议，要求每个结论有学生证据和导师证据
- [ ] `material-drafter`：把现有 `make_contact_email`、`make_ppt_outline` 等模板生成能力升级为草稿生成协议
- [ ] `material-reviewer`：把现有 `audit_material` 升级为 reviewer 协议，专门检查空泛、夸大、模板化和导师方向不贴合
- [ ] `evidence-auditor`：新增独立证据审计协议，逐句检查材料声明是否来自学生画像、导师来源或用户确认记录
- [ ] `interview-prep`：把现有 `make_interview_questions` 升级为面试准备协议，输出问题、追问、回答要点和不可编造边界
- [ ] `presentation-planner`：把现有 `make_ppt_outline` 和 `LocalPptxAdapter` 前置为 PPT 内容规划协议，后续对接 PPTAgent 或本地 PPTX 适配器
- [ ] `workflow-reporter`：把现有 `build_workspace_report` 升级为申请进度报告和演示案例报告协议

建议 skill 存放方式：

```text
.agents/skills/
└── grad-apply-workflow/
    ├── SKILL.md
    ├── workflows/
    │   ├── student-profile-intake.md
    │   ├── advisor-intake.md
    │   ├── advisor-match-review.md
    │   ├── material-drafter.md
    │   ├── material-reviewer.md
    │   ├── evidence-auditor.md
    │   ├── interview-prep.md
    │   ├── presentation-planner.md
    │   └── workflow-reporter.md
    └── references/
        ├── data-locations.md
        ├── evidence-rules.md
        └── safety-rules.md
```

可选薄指针目录：

```text
.codex/skills/
└── grad-apply-workflow.md

.claude/commands/
└── grad-apply.md
```

薄指针只负责提示对应运行时读取 `.agents/skills/grad-apply-workflow/SKILL.md`，不重复维护完整协议。

当前建议：

- 第一阶段直接写 `.agents/skills/grad-apply-workflow/`，让协议从一开始就是 portable skill
- 已创建 `.agents/skills/grad-apply-workflow/`，包含 `SKILL.md`、`workflows/`、`references/` 和 `agents/openai.yaml`
- 第一阶段暂不创建 `.codex/skills/` 和 `.claude/commands/` 薄指针入口，避免提前增加维护面
- 如果后续需要兼容 Codex/Claude Code 的原生发现机制，再增加薄指针入口；薄指针只指向 `.agents/skills/grad-apply-workflow/`
- skill 文件只写协议、输入输出、工具边界、禁止事项和验收清单，不复制业务代码
- 业务代码仍放在 `app/backend/` 和 `integrations/`，skill 负责指导 Agent 如何调用和审查这些能力

### 用户资料存储规划

当前已有存储：

```text
workspace/
├── profiles/
├── advisor_sources/
├── advisors/
├── targets/
├── matches/
├── applications/
├── generated/
├── quality_reports/
├── presentation_tasks/
└── reports/
```

已有存储判断：

- `generated/` 已经可以保存生成材料，但它更适合保存“当前可下载/可展示的材料”
- `quality_reports/` 已经可以保存质量检查结果，但它不是材料版本库
- 当前还没有专门保存“用户编辑前后版本”的清晰位置
- 因此需要新增 `material_versions/` 或类似目录，而不是把所有版本塞进 `generated/`

需要补充的原始资料区：

```text
workspace/
└── user_documents/
    ├── resumes/
    ├── transcripts/
    ├── research_projects/
    ├── publications/
    ├── awards/
    ├── personal_statements/
    └── misc/
├── material_versions/
└── agent_runs/
```

规划原则：

- [x] `user_documents/` 保存用户上传或粘贴的原始资料，不直接等同于结构化画像
- [x] `profiles/` 保存结构化学生画像，并记录来源 `document_id`
- [x] `material_versions/` 保存同一材料的 draft、reviewed、user_edited、final 等版本
- [x] `agent_runs/` 保存每次 drafter、reviewer、auditor 的输入摘要、输出摘要、状态和错误
- [x] 学生画像字段级 `evidence_map` 已能追溯到 `user_documents/` 的 `document_id`
- [x] 学生画像字段级 `confirmation_map` 已记录 `unconfirmed`、`confirmed`、`rejected`、`needs_review`
- [x] 学生资料以本地上传或粘贴内容为主证据源
- [ ] 学生网页资料只能作为补充来源，例如个人主页、GitHub、Google Scholar、ORCID、论文页面、项目主页和获奖公示
- [ ] 网页发现的学生信息不得直接覆盖本地资料，必须标记为外部来源并等待用户确认
- [ ] 用户确认后的网页信息才可以写入正式 `StudentProfile`
- [ ] 导师资料以网页来源为主，包括导师主页、实验室主页、招生通知、论文主页和学校教师主页
- [ ] 导师网页抓取失败时，必须支持手动粘贴正文作为兜底
- [ ] 导师字段、招生信息和研究方向必须保留 URL 或手动来源证据
- [ ] 学生资料和导师资料采用不同的来源优先级，不能使用同一套覆盖规则
- [ ] `workspace.example/` 只放匿名样例，不放真实学生资料
- [ ] `.gitignore` 和 security guard 必须继续保护 `workspace/` 和 `.env`
- [ ] 记录用户编辑前后版本时，必须在隐私说明中明确默认本地保存、默认不用于公开训练

资料来源优先级：

```text
学生资料：
本地上传/粘贴
-> 网页补充
-> 用户确认
-> 写入 StudentProfile

导师资料：
网页抓取
-> 抓取失败时手动粘贴
-> 保存来源证据
-> 写入 AdvisorSource / AdvisorProfile
```

### 本地资料格式与读取规范

本地资料允许存在的形式：

- 原始文件上传
- 手动粘贴文本
- 用户确认后的结构化画像
- 材料生成和编辑版本

允许的原始文件格式：

```text
.pdf
.docx
.md
.txt
.json
.csv
.xlsx
.png
.jpg
.jpeg
```

推荐目录映射：

```text
workspace/user_documents/
├── resumes/              # 简历
├── transcripts/          # 成绩单、排名证明
├── research_projects/    # 科研项目材料
├── publications/         # 论文、投稿说明、预印本说明
├── awards/               # 竞赛、奖项、证书
├── personal_statements/  # 个人陈述、研究计划草稿
├── manual_inputs/        # Web UI 手动粘贴内容
├── web_supplements/      # 用户个人网页补充来源
└── misc/                 # 其他补充材料
```

命名规则：

- [x] 上传文件保留原始扩展名
- [x] 文件名应使用安全文件名，去除路径分隔符和控制字符
- [x] 同名文件使用时间戳或内容 hash 区分
- [x] 手动粘贴内容保存为 `.txt`
- [ ] 网页补充来源必须保存 URL、抓取时间、正文摘要和可信度
- [ ] 不在文件名中暴露身份证号、手机号、完整邮箱等敏感信息

建议新增 manifest：

```text
workspace/user_documents/manifest.json
```

manifest 记录每份本地资料的元信息，而不是让 Agent 随意扫描目录。

示例结构：

```json
{
  "documents": [
    {
      "document_id": "doc_001",
      "category": "resume",
      "path": "user_documents/resumes/resume_20260817.pdf",
      "original_filename": "resume.pdf",
      "source_type": "local_upload",
      "content_hash": "sha256:...",
      "uploaded_at": "2026-08-17T10:00:00+08:00",
      "trusted": true,
      "confirmed": false,
      "notes": ""
    }
  ]
}
```

读取责任边界：

- [x] 后端代码负责真实上传、保存、列出、读取和 hash 计算
- [ ] portable skill 不直接替代后端存储逻辑
- [ ] portable skill 负责规定 Agent 读取顺序、可信规则、用户确认规则和输出格式
- [ ] Agent 不应绕过 manifest 随意遍历 `workspace/`
- [ ] Agent 读取学生资料时应先读取 `workspace/user_documents/manifest.json`
- [ ] Agent 只能读取 manifest 中登记过的资料路径
- [x] 如果 manifest 缺失，后端返回空 manifest；后续可补重建工具
- [x] 写入正式 `StudentProfile` 前必须经过用户确认或明确标记为未确认字段
- [x] `StudentProfile` 已记录 `source_document_ids` 和字段级 `evidence_map`
- [x] `StudentProfile` 已记录字段级 `confirmation_map`，前端可保存确认、未确认、否认和需复核状态

推荐读取流程：

```text
后端上传/粘贴落盘
-> 写入 user_documents/manifest.json
-> student-profile-intake skill 读取 manifest
-> 按 category 读取相关资料
-> 抽取候选画像字段
-> 标记来源 document_id 和置信度
-> 展示冲突和不确定项
-> 用户确认
-> 写入 profiles/
```

skill 与代码的分工：

```text
FastAPI / storage / services:
负责文件系统操作、内容读取、格式解析、hash、JSON 写入

.agents/skills/grad-apply-workflow/:
负责 Agent 工作协议、读取顺序、证据规则、禁止事项、质量验收清单

app/backend/agents/:
负责 drafter-reviewer-auditor 编排，按 skill 协议调用后端能力
```

建议新增目录：

```text
app/backend/agents/
├── base.py
├── advisor_extraction_agent.py
├── match_analysis_agent.py
├── material_draft_agent.py
├── material_review_agent.py
├── evidence_audit_agent.py
└── workflow_events.py
```

任务：

- [x] 定义 `AgentRun` 数据结构：输入、输出、状态、错误、开始时间、结束时间
- [x] 定义 `WorkflowEvent` 持久化结构，不只保存在内存
- [x] 第一条 Agent 主链路先做套磁邮件：`MaterialDraftAgent -> MaterialReviewAgent -> EvidenceAuditAgent`
- [x] `MaterialDraftAgent` 调用现有 `make_contact_email` 作为未配置 LLM 时的 fallback
- [x] 新增 `MaterialReviewAgent`，负责检查空泛、夸大、导师方向不贴合和面试不可解释
- [x] 新增 `EvidenceAuditAgent`，负责校验材料声明是否来自学生画像或导师来源
- [x] 支持 drafter-reviewer-auditor 三阶段输出：草稿、审稿意见、证据审计、修订稿、最终质量报告
- [x] 保存每次材料版本到 `material_versions/`，最终稿再写入 `generated/`
- [x] 为每次工作流运行记录输入摘要、输出摘要、质量分和风险标签
- [x] 增加 `workflow_events/`，记录 workflow_started、draft/review/audit、quality 和 final_saved 事件
- [x] 增加 `GET /api/agent-runs/{run_id}/events` 查询单次 Agent 运行事件
- [x] 套磁邮件 Evidence Auditor 已检查未确认学生字段，并将其写入 `needs_confirmation`
- [x] 套磁邮件生成器已避开用户标记为 `rejected` 的学生字段
- [x] 前端学生画像页已支持字段级确认状态保存
- [ ] 第二阶段再将导师资料解析拆成 `AdvisorExtractionAgent`，保留规则解析作为 fallback
- [ ] 第二阶段再将匹配分析拆成 `MatchAnalysisAgent`，输出维度评分、证据引用和风险项
- [ ] 设计后续 RL 数据采集字段，但默认不把真实用户数据用于公开训练
- [x] 增加单元测试覆盖 Agent fallback、review fail、evidence fail、LLM 未配置四类路径

验收标准：

- [x] 生成套磁邮件时，系统能返回 draft、review、final、quality_report 四类结果
- [x] LLM 未配置时仍能走规则模板和本地质量检查
- [x] reviewer 能明确指出材料中缺证据、太模板化或不可面试解释的句子
- [x] 每个 Agent 运行都有可追踪事件记录
- [x] 未确认学生字段不会阻断草稿生成，但会出现在质量报告和 Evidence Auditor 提醒中
- [x] 用户已否认字段不会被套磁邮件生成器主动使用；如果材料中仍出现，Evidence Auditor 标记为不通过

### 大模型能力演进规划

当前项目不一次性引入 PPTAgent 的全部模型依赖，而是保留清晰的能力演进路线。

#### 阶段 L0：当前 MVP，轻量文本 API

已有或优先保留：

- [x] OpenAI-compatible API
- [x] Responses API 和 Chat Completions API 兼容
- [x] 文本输入
- [x] JSON 结构化输出
- [x] 规则 fallback
- [ ] 统一 `LLMProvider` / `LLMClient`
- [ ] 超时、429、5xx 和 JSON 解析失败重试
- [ ] 记录模型名、任务名、耗时、状态和错误

适用任务：

```text
导师资料抽取
套磁邮件 drafter
材料 reviewer
证据 auditor
匹配分析
```

#### 阶段 L1：异步调用和并发

触发条件：

- [ ] 一次请求需要同时处理多个导师
- [ ] 一次生成需要并行审查多个材料
- [ ] PPT 页面或图片任务明显拖慢整体流程

规划能力：

- [ ] 增加 `AsyncLLMClient`
- [ ] 支持多个独立 Agent 任务并发
- [ ] 支持任务级超时、取消和失败重试
- [ ] 使用本项目自有并发控制，不直接引入 PPTAgent 的 `oaib`
- [ ] 只有在确认供应商批量接口有明显收益后，才增加 batch provider

#### 阶段 L2：视觉模型

适用任务：

```text
成绩单截图读取
科研项目图理解
论文图表说明
参考 PPT 页面分析
面试 PPT 可读性检查
```

规划能力：

- [ ] `VisionProvider` 与 `TextProvider` 分离
- [ ] 统一输入图片路径、MIME 类型和大小限制
- [ ] 图片调用结果保存 caption、摘要、模型和来源
- [ ] 视觉模型失败时回退到 OCR、文本解析或人工确认
- [ ] 默认不让视觉模型直接改写学生事实

依赖边界：

- 不在 MVP 中引入 `torch`
- 不在 MVP 中引入本地视觉模型
- 先使用 OpenAI-compatible vision API
- 只有需要本地推理、批量图片 embedding 或离线处理时，才评估 PyTorch/Transformers

#### 阶段 L3：Embedding 和相似度检索

适用任务：

```text
导师论文与学生项目相似度检索
相似科研经历召回
材料版本去重
导师来源段落检索
历史 Agent 反馈检索
```

规划能力：

- [ ] 增加独立 `EmbeddingProvider`
- [ ] 记录 embedding 模型、维度和数据版本
- [ ] 先使用 API embedding，不默认引入 PyTorch
- [ ] 使用轻量余弦相似度实现第一版检索
- [ ] 数据量达到本地检索瓶颈后，再评估 FAISS 或向量数据库
- [ ] embedding 只用于检索和辅助排序，不直接替代证据审计

#### 阶段 L4：批量推理

适用任务：

```text
批量分析多个导师
批量生成多份材料候选
批量处理参考 PPT 页面
离线评估大量 drafter/reviewer 样本
```

规划能力：

- [ ] 增加 `BatchProvider` 抽象
- [ ] 支持任务队列、批次 ID、单任务状态和部分失败
- [ ] 支持成本、吞吐和延迟统计
- [ ] 在线交互优先使用异步并发，离线评估再考虑供应商 batch API
- [ ] 不因为 PPTAgent 使用 `oaib` 就直接增加 `oaib` 依赖

#### 阶段 L5：图片生成

适用任务：

```text
非事实型背景图
通用装饰插图
演示文稿占位图
```

明确限制：

- [ ] 不用于生成学生经历、论文结果、成绩或科研事实
- [ ] 不用于伪造学校、实验室、导师或项目图片
- [ ] 默认关闭图片生成
- [ ] 生成图片必须标记为 AI-generated，并保存生成模型和 prompt
- [ ] 只有在 PPT 视觉质量确实需要时，才增加 `ImageGenerationProvider`

### 模型依赖决策表

| 能力 | 当前 MVP | 后续条件 | 主要用途 | 是否引入 PPTAgent 依赖 |
|---|---|---|---|---|
| 文本 API | 使用 | 当前必须 | 抽取、生成、reviewer、auditor | 否，重写轻量客户端 |
| 异步调用 | 暂缓 | 多任务耗时明显时 | 并发 Agent 调用 | 否，自研 `AsyncLLMClient` |
| Vision API | 暂缓 | 需要读取图片/PPT 时 | 图片理解、视觉审查 | 否，先接 OpenAI-compatible vision |
| Embedding API | 暂缓 | 需要相似度检索时 | 论文/项目/材料检索 | 否，先用 API embedding |
| PyTorch | 暂缓 | 本地视觉模型或大规模向量计算 | 本地模型、GPU、tensor | 不直接引入 |
| `oaib` | 暂缓 | 离线批量 API 有明确收益时 | batch 请求 | 不直接复制 |
| 图片生成 API | 暂缓 | PPT 视觉素材需求明确时 | 非事实型插图 | 独立 provider |

建议 commit：

```bash
git checkout -b feat/agent-review-workflow
pytest -q
git add app/backend/agents app/backend tests docs/03_execution_plan.md
git commit -m "feat(agent): add reviewable grad application workflow"
git push -u origin feat/agent-review-workflow
```

## 阶段 9：演示案例准备

目标：准备一个完整项目展示案例，用于简历、答辩或面试。

任务：

- [ ] 构造一个匿名学生样例
- [ ] 选择一个真实目标导师样例
- [ ] 保存导师主页/实验室主页/招生通知来源
- [ ] 准备输入材料
- [ ] 生成匹配报告
- [ ] 生成套磁邮件
- [ ] 生成面试展示 PPT
- [ ] 生成模拟面试题
- [ ] 生成申请状态 Dashboard
- [ ] 录制 Demo 或截图

最终演示路径：

```text
学生上传资料
-> 选择导师
-> 查看匹配分析
-> 生成套磁邮件
-> 生成面试 PPT
-> 查看模拟面试题
-> 更新申请状态
```

## 阶段 10：工程规范与开源安全守卫

目标：借鉴 `ai-job-search-master` 的工程约束，把项目从“能跑”提升到“可维护、可审计、适合开源展示”。

优先级：

- [x] 已确认马上加，不后置到 Agent 工作流之后
- [x] 先把工程守卫建起来，再继续扩展更复杂的 Agent 代码
- [x] 如果 ruff 引入格式化差异，单独使用一次 `chore` 提交，避免和业务逻辑混在一起

当前差距：

- CI 目前主要运行 pytest，缺少格式化、lint、安全守卫和文档一致性检查
- 项目没有统一 `pyproject.toml` 来固定 ruff、pytest、typing 等基础规则
- 已有 `test_no_secrets.py`，但还没有 `.gitignore` 必备规则、workspace 泄露、外部项目整目录复制等检查

任务：

- [x] 新增 `pyproject.toml`，统一 ruff、pytest、Python 版本和基础格式规则
- [x] 在 CI 中增加 `ruff check` 和 `ruff format --check`
- [x] 新增 `tools/security_guards.py`
- [x] 检查 `.env`、`workspace/`、真实成绩单、真实套磁邮件、真实导师联系记录不会进入 Git
- [x] 检查是否误提交外部参考项目整目录或大段复制代码
- [x] 检查 `NOTICE` 中外部项目引用边界是否存在
- [x] 新增 `tools/lint_docs.py`，检查 docs 中的 MVP/API/数据对象和代码模型是否明显漂移
- [x] 为 GitHub Actions 增加安全守卫和文档检查
- [x] 在 `CONTRIBUTING.md` 中写明分支、commit、测试和推送要求

建议 commit：

```bash
git checkout -b chore/engineering-guards
pytest -q
ruff check .
ruff format --check .
python tools/security_guards.py
git add pyproject.toml tools .github/workflows tests docs/03_execution_plan.md CONTRIBUTING.md
git commit -m "chore(ci): add lint and security guards"
git push -u origin chore/engineering-guards
```

## 阶段 11：PPTAgent 深度集成

目标：在保留本地 PPTX 兜底的基础上，逐步接入 PPTAgent 的参考模板学习、版式选择和评估能力。

当前判断：

- 当前 `LocalPptxAdapter` 已能生成可编辑 PPTX，适合 MVP
- 但它没有使用参考 PPT 模板、版式归纳、图片理解、PPTEval 等能力
- 不建议复制 PPTAgent 整目录；应通过适配器或可选外部运行时接入

阶段 11A：接口准备

- [ ] 扩展 `PresentationRequest`，支持 `reference_file`、`presentation_type`、`duration_minutes`、`asset_paths`
- [ ] 扩展 `PresentationResult`，记录生成引擎名称、fallback 原因和质量评分
- [ ] 前端支持上传参考 PPT 模板，但默认不强制使用
- [ ] 后端保存参考 PPT 文件 hash，避免重复处理

阶段 11B：PPTAgent 适配器

- [ ] 新增 `PptAgentAdapter`，只依赖本项目稳定接口
- [ ] 调用外部 PPTAgent 时使用独立运行目录，不把外部源码复制进本项目主代码
- [ ] 支持输入：保研 PPT Markdown 大纲 + 可选参考 PPTX + 可选学生/导师摘要
- [ ] 支持输出：PPTX 文件、生成日志、失败原因、fallback 到 `LocalPptxAdapter`
- [ ] 增加端到端样例验证，确认参考 PPT 路径、输出路径和失败回退都可用

阶段 11C：版式与评估

- [ ] 借鉴 PPTAgent 的 `planner / layout_selector / editor / coder` 分工，设计保研 PPT 专用子 Agent
- [ ] 增加 PPT 质量检查：页数、每页文字量、图片占位、标题长度、导师方向匹配、面试可解释性
- [ ] 后续评估是否接入 PPTEval 思路，优先输出轻量 JSON 评分，不先引入重依赖

建议 commit：

```bash
git checkout -b feat/presentation-engine-adapter
pytest -q
git add integrations app/backend app/frontend tests docs/03_execution_plan.md
git commit -m "feat(presentation): add optional PPTAgent adapter boundary"
git push -u origin feat/presentation-engine-adapter
```

## 关键未决问题

需要进一步和用户确认：

- [x] 第一版主要服务保研中的硕博申请
- [x] 第一版以中文为主，英文材料作为扩展
- [x] 需要真实导师信息
- [x] 真实导师信息第一版采用“URL 抓取 + 手动粘贴兜底”
- [x] 不直接改造原外部申请流程项目，以借鉴和局部底层复用为主
- [x] 演示文稿生成能力优先通过适配层直接调用；如果依赖不稳定，再以中间文件方式降级
- [x] 最终代码框架不允许出现借鉴项目复制体，代码命名也避免直接使用原项目名
- [x] 第一版不把强化学习放进 MVP
- [x] 需要规划 MVP 之后的强化学习接入
- [ ] 是否需要做简历项目展示用的视频或截图？
- [x] 可复用 skill 从一开始采用 portable 结构，优先放在 `.agents/skills/grad-apply-workflow/`
- [x] 第一阶段不提供 `.codex/skills/` 或 `.claude/commands/` 薄指针入口，后续按需要再加
- [x] Agent 工作流第一优先级确定为“套磁邮件 drafter-reviewer-auditor”
- [x] 用户原始资料需要落盘，新增 `workspace/user_documents/`
- [x] 用户编辑前后版本需要记录，新增 `workspace/material_versions/`
- [x] 马上新增 `pyproject.toml`、ruff、更严格 CI 和 security guards
- [ ] PPTAgent 深度集成是否要求真实接入外部项目运行时，还是先保留可选适配器接口？

## 当前建议

当前已经完成工程守卫、portable skill 主目录、用户原始资料落盘、字段级证据、字段级确认状态、套磁邮件 `MaterialDraftAgent -> MaterialReviewAgent -> EvidenceAuditAgent` 主链路，以及独立质量检查模块。

建议下一步进入第二条 Agent 链路：

```text
AdvisorExtractionAgent
-> MatchAnalysisAgent
-> 字段证据和质量检查复用
-> 准备阶段 9 的匿名演示案例
```

继续保持当前边界：不把参考项目复制进最终代码框架，以本项目自有保研业务代码为主体，只在必要位置保留适配器和可审计的底层复用。PPTAgent 深度集成仍后置到阶段 11。
