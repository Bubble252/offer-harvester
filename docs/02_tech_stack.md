# 技术栈与模块设计

## 技术选型原则

本项目以自有代码为主，适度借鉴现有项目的架构、流程和底层模块。

技术选型原则：

- 借鉴已有申请流程项目的评估框架和归档思路
- 通过适配层调用或复用已有演示文稿生成项目的 PPT 生成链路
- 对业务代码保持保研场景自有实现，避免被求职项目的数据结构和命令体系绑死
- 只有底层功能清晰、依赖较少、迁移成本低的模块才直接复用
- 最终代码框架不允许出现借鉴项目的项目复制体，代码包名也避免直接使用原项目名
- 第一阶段使用本地文件存储，降低系统复杂度
- 第一阶段不引入复杂权限、多租户和云端部署
- 先跑通单用户完整闭环，再扩展成平台

## 代码复用与命名策略

### 命名约束

文档中可以明确写出参考了哪些项目、哪些模块和哪些设计点，便于审计和说明技术来源。

最终代码中的目录名、包名、类名、API 路径、测试名应使用中性命名，避免直接出现借鉴项目原名。

推荐命名：

- `workflow_engine`：申请流程、状态、报告相关适配器
- `presentation_engine`：PPT 生成、模板、任务相关适配器
- `document_pipeline`：文档解析、清洗、证据抽取
- `generation_pipeline`：材料生成和审查链路

不推荐命名：

- 直接使用原求职项目名作为目录或包名
- 直接使用原 PPT 项目名作为目录或包名
- 使用 `*_copy`、`vendor_*`、`fork_*` 等暗示复制体的目录名

### 注释规范

代码注释必须符合工程规范：

- 注释解释“为什么这样做”和“边界条件”，不复述代码表面含义
- 不在业务代码中写“复制自某项目”“照搬某项目”等表述
- 如果确实复用或改写了单个外部函数，必须在文件头或 `NOTICE` 中按许可证要求标注来源
- 不保留大段外部项目原注释
- 不用注释记录临时调研过程，调研记录写在 `docs/` 中
- 适配器注释应说明契约、输入输出、降级行为和失败处理
- 涉及隐私和安全的逻辑必须有简短注释说明风险边界

推荐注释示例：

```python
# Keep raw source text so generated recommendations can be traced back during review.
```

不推荐注释示例：

```python
# This is copied from the PPT project.
# Loop through items and append them to the list.
```

### 申请流程参考项目

使用策略：

- 主要借鉴流程，不直接改造原项目
- 迁移时优先抽象自己的保研数据模型
- 对求职强相关模块只参考，不搬运
- 最终项目中不得保留外部申请流程项目的整目录复制

可考虑复用：

- tracker / 状态记录思路
- HTML report 生成方式
- PDF 验证、文本抽取、测试用例结构
- drafter-reviewer 工作流设计
- 文档归档目录设计

不直接复用：

- job portal scraper
- 求职岗位评分维度
- CV / cover letter 模板正文
- Claude Code 专用命令文件
- 与丹麦求职市场相关的工具

### 演示文稿生成参考项目

使用策略：

- 优先通过适配器调用现有 PPT 生成能力
- 保研业务层自己实现，不直接套用原 UI
- 如果底层 PPT 解析/生成函数边界清晰，可逐步模块化复用
- 最终项目中不得保留外部演示文稿项目的整目录复制；只保留适配器、接口定义和必要的自有封装

可考虑复用：

- PPTX/PDF 上传解析
- `runs` 任务目录管理
- WebSocket 进度上报
- PPTX 生成和下载
- 参考模板学习能力

需要谨慎处理：

- 原项目依赖较多，环境稳定性需要先验证
- 原前端较简单，不适合直接作为保研工作台 UI
- 强化学习版本目前独立于主链路，不放进 MVP 主依赖

## 总体架构

建议架构如下：

```text
Frontend Web UI
  |
  | HTTP / WebSocket
  v
FastAPI Backend
  |
  |-- Profile Service
  |-- Advisor Source Service
  |-- Target Service
  |-- Matching Service
  |-- Material Generation Service
  |-- Interview Prep Service
  |-- Presentation Generation Adapter
  |-- RL Training Adapter (later)
  |-- Tracker / Report Service
  |
  v
Local Workspace Storage
  |
  |-- profiles/
  |-- advisor_sources/
  |-- targets/
  |-- applications/
  |-- generated/
  |-- ppt_runs/
```

第一阶段可以不拆成微服务，只在代码层面拆模块。

## 前端技术栈

现有演示文稿参考项目的前端使用 Vue；本项目可以采用 Vue 技术栈，但不直接复用其业务 UI。

建议：

- Vue 3
- Vue Router
- Axios
- 原生 CSS 或轻量 UI 组件库
- WebSocket 展示长任务进度

核心页面：

- 学生档案页
- 资料上传页
- 真实导师资料页
- 目标导师/项目池
- 目标详情页
- 匹配分析页
- 材料生成页
- PPT 生成页
- 面试准备页
- 申请状态看板
- 报告导出页

第一版应建立本项目自己的 Web UI，不在参考项目的前端目录上直接扩展。

## 后端技术栈

现有演示文稿参考项目后端使用 FastAPI，本项目后端也采用 FastAPI。

建议：

- Python 3.11
- FastAPI
- Uvicorn
- Pydantic
- Python multipart 文件上传
- WebSocket 任务进度
- Markdown 文件作为中间产物
- JSON/CSV 作为状态存储

后续如果需要平台化，可加入：

- SQLite 或 PostgreSQL
- SQLAlchemy
- Celery / Redis Queue
- 对象存储
- 用户登录与权限控制

## AI 能力模块

### 1. 学生画像抽取

输入：

- 简历
- 成绩单
- 论文/项目材料
- 竞赛证明
- 个人陈述草稿

输出结构：

```json
{
  "basic_info": {},
  "education": [],
  "research_interests": [],
  "projects": [],
  "publications": [],
  "competitions": [],
  "skills": [],
  "awards": [],
  "strengths": [],
  "risks": []
}
```

可借鉴申请流程参考项目的 profile setup 思路。

### 2. 目标导师/项目解析

输入：

- 导师主页 URL 或文本
- 实验室主页 URL 或文本
- 招生简章 URL 或文本
- 夏令营通知 URL 或文本
- 论文列表、Google Scholar、学校教师主页等真实来源
- 用户手动填写信息

输出结构：

```json
{
  "target_type": "advisor|program|camp|school",
  "school": "",
  "department": "",
  "advisor": "",
  "source_urls": [],
  "source_texts": [],
  "research_topics": [],
  "recent_publications": [],
  "requirements": [],
  "deadline": "",
  "contact_email": "",
  "materials_required": [],
  "notes": []
}
```

第一阶段必须支持真实导师信息，采集方式确定为“URL 抓取 + 手动粘贴兜底”。

- 用户粘贴导师主页、招生通知、论文主页等 URL
- 系统尝试抓取正文
- 如果抓取失败，允许用户粘贴网页正文
- 所有解析结果保留来源字段
- 生成材料时引用来源，不把模型推测当成事实

可选来源字段：

```json
{
  "source_id": "",
  "source_type": "advisor_homepage|lab_homepage|admission_notice|publication_page|manual_text",
  "url": "",
  "title": "",
  "fetched_at": "",
  "fetch_status": "success|failed|manual",
  "content_hash": "",
  "trusted": true
}
```

### 3. 匹配度评估

评估维度：

- 研究方向匹配
- 导师近期论文方向匹配
- 项目经历匹配
- 成绩背景匹配
- 技术能力匹配
- 学术成果匹配
- 申请材料完整度
- 面试风险
- 套磁建议

第一版以稳妥匹配为主，因此评分不鼓励夸大“冲刺”。推荐 tier：

- `strong_fit`：经历证据充分，方向高度一致
- `reasonable_fit`：方向相关，有材料可支撑
- `weak_fit`：存在明显短板，不建议作为主投目标
- `unknown`：导师信息不足，需继续补充真实资料

输出：

```json
{
  "fit_score": 82,
  "tier": "strong_fit|reasonable_fit|weak_fit|unknown",
  "evidence": [],
  "gaps": [],
  "recommended_actions": [],
  "material_strategy": []
}
```

可借鉴申请流程参考项目的 fit scoring 思路。

### 4. 材料生成

生成类型：

- 套磁邮件
- 中文简历摘要
- 英文 CV 摘要
- 个人陈述大纲
- 研究计划大纲
- 推荐信素材
- 面试自我介绍
- 项目介绍稿

生成原则：

- 不编造用户未提供的信息
- 每个主张都尽量关联证据
- 面向目标导师方向定制
- 保留用户可编辑的 Markdown 源文件
- MVP 输出以中文为主，英文材料作为扩展接口保留

### 5. 面试准备

输出内容：

- 3 分钟自我介绍
- 5 分钟自我介绍
- 科研项目讲解稿
- 导师方向相关追问
- 简历深挖问题
- 英语面试问题
- 行为面试问题
- 不足项解释策略

可借鉴申请流程参考项目的 interview prep 思路。

### 6. 演示文稿生成适配器

演示文稿生成接入点：

- 输入用户材料和目标导师分析
- 生成 PPT 大纲
- 生成每页内容
- 选择参考 PPT 模板
- 输出可编辑 PPTX

建议先新增适配层，不直接大改参考项目核心代码：

```text
grad-apply-workflow
  -> 生成 intermediate markdown/json
  -> 调用 presentation_engine 生成 PPTX
```

目标 PPT 类型：

- `self_intro_3min`
- `self_intro_5min`
- `research_project`
- `research_plan`
- `advisor_interview`

MVP 中演示文稿生成能力的接入方式：

- 优先直接调用其后端生成能力，而不是让用户手动切换到原项目
- 如果环境或依赖不稳定，先用中间 Markdown/JSON 生成升学 PPT 内容，再保留 presentation_engine 接口占位
- 接入前必须完成一次本地可运行验证

## 数据目录设计

建议目录结构：

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
│   ├── templates/
│   └── reports/
└── integrations/
    ├── workflow_engine/
    └── presentation_engine/
```

`integrations/` 的定位不是存放外部项目复制体，而是存放自有适配层：

- `integrations/workflow_engine/`：放流程映射、tracker/report 等自有包装，不复制原项目
- `integrations/presentation_engine/`：放演示文稿生成调用适配器、请求/响应模型、降级逻辑，不复制原项目

如果调研阶段需要临时引用原项目源码，应放在仓库外部或明确标记为中间产物，不进入最终代码框架。

### MVP 本地 PPTX 输出

阶段 6 使用本项目自有的 `python-pptx` 适配器生成可编辑 PPTX：

- 输入：已生成的 5 页中文 Markdown 面试大纲
- 输出：16:9 宽屏、原生文本框和色块可编辑的 PPTX
- 主题：紫罗兰色为主，深色正文，面向导师面试的克制学术风格
- 接口：`POST /api/targets/{target_id}/ppt`、`GET /api/tasks/{task_id}`、`GET /api/tasks/{task_id}/download`
- 任务状态：`queued`、`running`、`completed`、`failed`

该实现不依赖外部 LLM、视觉模型或参考项目运行时。未来如配置独立的 Python 3.11 演示文稿引擎，可在同一中性适配器契约后增加增强实现；不把其源码、包名或业务 UI 引入本项目。

第一阶段可以只建立 `docs/`，后续逐步实现自有代码和适配器。

## 状态跟踪模型

申请状态建议使用以下枚举：

```text
draft
researching
ready_to_contact
contacted
replied
materials_preparing
submitted
shortlisted
interview_scheduled
interview_done
accepted
rejected
withdrawn
```

字段建议：

```json
{
  "target_id": "",
  "target_name": "",
  "school": "",
  "advisor": "",
  "status": "",
  "deadline": "",
  "last_contact_at": "",
  "next_action": "",
  "materials": [],
  "notes": []
}
```

## 与强化学习模块的关系

参考项目中的强化学习模块目前适合定位为：

> 结构化材料生成优化模块。

可以用于优化：

- 个人陈述大纲
- 研究计划大纲
- 自我介绍 PPT 大纲
- 科研展示内容结构
- 套磁邮件结构

但第一阶段不建议把强化学习作为主流程依赖。原因：

- 当前训练数据量较小
- 当前模型未接入演示文稿生成主链路
- 训练和部署成本较高
- MVP 更需要稳定流程，而不是先追求训练效果

MVP 阶段先以 prompt + reviewer 工作流实现，后续再把 RL 模块作为可选增强。

## 后续强化学习接入规划

强化学习不进入 MVP 主链路，但需要提前保留数据接口。

### 阶段 A：数据积累

在 MVP 中记录以下数据：

- 学生画像摘要
- 真实导师资料摘要
- 匹配分析结果
- 生成的大纲和材料
- 用户修改后的最终版本
- 材料质量检查结果
- 面试反馈或申请结果

这些数据后续可形成偏好数据和奖励信号。

### 阶段 B：离线评估集

建立保研材料评估集：

- 套磁邮件样本
- 个人陈述大纲
- 研究计划大纲
- 面试 PPT 大纲
- 科研项目介绍结构

评估维度：

- 与导师方向匹配
- 事实一致性
- 结构完整性
- 表达克制程度
- 面试可解释性
- 稳妥申请策略一致性

### 阶段 C：奖励函数设计

可设计两类奖励。

规则奖励：

- 是否引用真实导师来源
- 是否避免虚构经历
- 是否覆盖学生强证据经历
- 是否避免过度承诺
- 是否符合套磁邮件/个人陈述/PPT 大纲格式

LLM-as-Judge 奖励：

- 导师方向匹配度
- 材料说服力
- 语气是否稳妥
- 是否像真实学生材料
- 是否存在夸大风险

### 阶段 D：接入点

优先训练和接入以下模块：

- `advisor_match_outline_model`：生成导师匹配分析结构
- `email_draft_policy_model`：生成稳妥型套磁邮件
- `interview_ppt_outline_model`：生成面试 PPT 大纲
- `research_plan_outline_model`：生成研究计划大纲

不优先训练：

- PPT 排版模型
- 自动录取判断模型
- 端到端保研 Agent

### 阶段 E：上线方式

上线时不替换整个系统，而是作为可选生成策略：

```text
Prompt Baseline
-> Reviewer Check
-> RL-Optimized Draft
-> Reviewer Check
-> User Final Edit
```

只有当离线评估证明 RL 版本在事实一致性、导师匹配和材料质量上稳定优于 baseline，才进入默认链路。

## 质量控制与安全边界

必须加入的校验：

- 事实一致性检查
- 导师来源引用检查
- 材料完整性检查
- 导师方向匹配检查
- 过度包装风险检查
- 模板化表达检查
- PPT 页数和可读性检查

系统不应：

- 编造论文、成绩、奖项
- 自动代发邮件
- 声称保证录取
- 输出不透明的录取概率
- 替代学生做最终申请判断

## 依赖现状

已知参考来源：

- 外部申请流程项目：用于流程、状态、报告、审查链路参考
- 外部演示文稿生成项目：用于 PPT 生成、模板归纳、任务进度参考

第一阶段需要进一步确认：

- 外部申请流程项目的命令和工具是否完整存在
- 外部演示文稿生成项目当前环境是否可运行
- 外部演示文稿生成项目是否已有可用模型 API 配置
- 本地是否安装生成 PPT 所需依赖
- 前端是否需要重构或可以直接复用
- 真实导师网页抓取是否受网络和反爬限制影响
- 是否需要为导师资料来源建立人工校验流程
