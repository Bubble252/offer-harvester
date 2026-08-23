# 文枢行政助手 Agent 参考分析

本文档由外部项目 `/home/bubble/agent/居丽叶的简历项目9：行政助手Agent/wenshu-project/` 的阅读结果转换而来，用于记录本项目可以借鉴的技术栈、架构思想和明确不照搬的边界。

## 项目定位

文枢项目是一个面向学校多部门文档的行政助手系统，核心链路是：

```text
部门文档入库
-> 文档解析、切块、索引
-> RAG 问答
-> 答案证据校验
-> 部门审核
-> 反馈沉淀为 skill / hook / rule
```

它的业务目标和我们的保研申请项目不同，但它在 RAG、Agent 编排、证据审计、记忆分层和反馈闭环上的设计值得参考。

## 目录结构

| 路径 | 作用 |
| --- | --- |
| `backend/` | Python FastAPI 后端，负责认证、文档解析、切块、索引、RAG、记忆治理、审核、任务队列和 API。 |
| `web/` | Next.js + React 前端，包含聊天界面、后台管理界面、Loop/Skill 可视化等。 |
| `services/pi-agent/` | Node.js/TypeScript Agent 服务，基于 pi-agent 生态封装 LLM 调用和工具调用。 |
| `docs/` | 架构、API、部署、变更审计、Loop Engineering 等说明文档。 |
| `deploy/` | Docker Compose、Kubernetes、监控和生产部署材料。 |
| `department_files/` | 示例部门文档，用于本地演示和入库测试。 |
| `backend/tests/` | 后端测试，覆盖认证、切块、检索、RAG、Loop、记忆、审核、任务队列等。 |
| `backend/scripts/` | 数据初始化、文档入库、RAG 评测、异步 worker、Loop worker、依赖检查等脚本。 |
| `loadtest/` | 压测脚本和结果对比工具。 |
| `design_files/` | 架构图、部署图、使用指南和技术方案资料。 |

## 技术栈

| 层次 | 技术 |
| --- | --- |
| 后端 | FastAPI、Uvicorn、Pydantic、MongoDB、Redis |
| 文档处理 | pypdf、pdfplumber、python-docx、BeautifulSoup、PaddleOCR 可选 |
| 检索 | BM25、jieba、向量检索、RRF、reranker 可选 |
| LLM | DeepSeek / OpenAI-compatible API / Relay Provider |
| Embedding | text-embedding-3-large、hash embedding fallback |
| 前端 | Next.js 15、React 19、TypeScript |
| Agent 服务 | Node.js、TypeScript、Fastify、`@earendil-works/pi-agent-core`、`@earendil-works/pi-ai` |
| 部署 | Docker Compose、Kubernetes、Prometheus、Grafana |
| 测试 | pytest、pytest-asyncio、browser smoke |

## 核心架构

### 控制面与执行面分离

文枢把 Python 后端作为确定性控制面，把 pi-agent 服务作为概率性执行面：

- Python 后端负责权限、数据、RAG、记忆治理、审核流程、任务状态、部署回滚。
- pi-agent 负责 LLM 相关动作，例如意图识别、问题改写、答案生成、答案校验、反思和工具调用。
- Agent 服务不直接决定权限，也不直接读取数据库，避免 LLM 侧绕过业务规则。

本项目应借鉴这个边界：FastAPI 后端掌握事实来源、字段确认状态、证据审计和工作流状态；LLM 只产出候选草稿、改写、评分和解释，不直接写入可信 profile 或知识库。

### 固定 DAG 工作流

文枢问答链路大致是：

```text
Intent
-> Rewrite
-> Retrieval
-> Answer
-> Verify
-> Retry / Feedback
```

本项目已经有：

```text
MaterialDraftAgent
-> MaterialReviewAgent
-> EvidenceAuditAgent
```

后续可以借鉴文枢，把检索、校验和重试显式化：

- `ProfileFactRetrieval`：从用户资料、导师资料、知识库检索证据。
- `MaterialDraftAgent`：只根据输入事实和证据生成草稿。
- `MaterialReviewAgent`：检查表达、结构、目标匹配度。
- `EvidenceAuditAgent`：检查关键事实是否有证据、字段是否 confirmed。
- `Retry/Revision`：高风险草稿返回 drafter 修改，而不是直接交给用户。

### RAG 管线

文枢的 RAG 管线包括解析、清洗、语义切块、元数据索引、BM25/向量混合检索、可选 reranker 和证据约束。对本项目，RAG 应服务三类信息：

- 学生资料 RAG：简历、成绩单、项目经历、论文、奖项证明、个人陈述草稿。
- 导师/项目信息 RAG：导师主页、论文、实验室介绍、招生要求、公开评价。
- 保研常识/政策 RAG：推免流程、报名截止日期、夏令营/预推免规则、材料要求、学校学院通知。

### 记忆与事实分层

本项目可以把文枢的事实/记忆分层改造成：

- 学生事实平面：用户上传或粘贴的原始资料、字段证据、字段确认状态。
- 导师事实平面：导师主页、论文、招生信息、实验室资料、人工确认过的来源。
- 申请知识事实平面：保研流程、学校通知、截止日期、材料清单。
- 工作记忆：当前一次材料生成或导师匹配任务的上下文。
- 用户偏好记忆：用户偏好的语气、目标地区、学校层次、导师风格。
- Agent 反馈记忆：失败案例、审计问题、用户修改意见。
- Portable Skill 记忆：可迁移的写作、审核、证据检查、导师分析技能。

建议权威性顺序：

1. 用户确认过的本地原始资料和字段。
2. 官方导师主页、学院官网、招生通知。
3. 人工审核过的保研知识库条目。
4. 未确认但有来源的用户上传/粘贴资料。
5. 网页补充资料。
6. LLM 生成内容。

LLM 生成内容不能自动成为事实，必须经过证据绑定和确认。

## 可借鉴点

### 轻量 RAG

第一版建议只借鉴思路，不复制完整实现：

- 用本地 JSON/SQLite 保存知识库条目和 chunk。
- 第一版先做 BM25/关键词检索 + 元数据过滤。
- 每条 chunk 保存 `source_type`、`source_path`、`owner`、`created_at`、`effective_date`、`confidence`。
- 输出材料时，将关键事实映射到证据。
- 后续再加入 embedding、reranker、Chroma/Milvus。

适合落到本项目的目录：

```text
app/backend/rag/
app/backend/knowledge_base/
workspace/user_documents/
workspace/knowledge_base/
workspace/rag_index/
```

### 文档切块策略

文枢按“标题、条款、章节路径”切块。保研项目也不应简单按字符切块：

- 简历：按教育经历、科研经历、项目经历、奖项、技能切块。
- 成绩单：按课程、绩点、排名、核心课成绩切块。
- 论文/项目：按标题、贡献、方法、结果、证明材料切块。
- 导师网页：按简介、研究方向、招生要求、论文、实验室介绍切块。
- 保研政策：按学校、学院、年份、批次、截止日期、材料要求切块。

### 审核闭环

文枢的新文档审核机制可以改造成保研知识库治理：

- 新增学校/学院政策条目后，系统生成 3-5 个校验问题。
- 系统基于该条目回答，并展示引用片段。
- 用户或管理员确认后，条目进入可信知识库。
- 未确认条目可用于草稿提醒，但不能作为强事实写入最终材料。

### Trace 与质量报告

建议借鉴为：

- 每次生成材料保存一次 workflow event。
- 记录 drafter 输入、reviewer 修改建议、auditor 发现的问题。
- Quality report 展示未确认事实、无证据事实、过时政策、来源冲突。
- 后续用这些记录沉淀可复用 skill。

### Skill / Hook / Rule 演化

文枢把反馈转化为 skill、hook、rule。保研项目可转化的 portable skill：

- `material-drafter`：套磁邮件、个人陈述、研究计划草稿。
- `material-reviewer`：结构、语气、目标导师匹配度。
- `evidence-auditor`：事实来源、字段确认状态和引用可靠性。
- `advisor-profiler`：导师画像抽取与证据整理。
- `match-rubric`：导师/项目匹配评分规则。
- `deadline-checker`：学校/学院截止日期和材料清单检查。
- `profile-field-normalizer`：用户资料字段抽取、证据绑定、确认状态标记。

### 评测意识

本项目也应建立小型固定评测集：

- 给定导师主页，能否正确抽取研究方向、邮箱、招生要求。
- 给定学生简历，能否正确抽取 GPA、排名、论文、项目经历。
- 给定学校通知，能否正确回答截止日期、材料清单、报名入口。
- 给定一封套磁邮件，能否指出所有未确认事实。

第一版不需要复杂 benchmark，但应保留 10-20 条固定样例，避免后续改动导致质量倒退。

## pi-agent 借鉴边界

可以借鉴：

- 控制面/执行面分离。
- 固定 DAG。
- LLM 工具调用集中在执行面。
- Agent 输出结构化，由后端做权限、证据和状态管理。
- feedback -> skill/rule 候选的循环。

暂不直接引入：

- `services/pi-agent/` 作为本项目必需服务。
- `@earendil-works/pi-agent-core` / `@earendil-works/pi-ai` 作为默认依赖。
- Node Agent 服务和 Python 后端之间的跨服务部署。
- Agent 自动写入可信 profile、正式知识库或最终材料。

推荐路线：

```text
短期：
Python FastAPI 内继续实现 Agent DAG。

中期：
抽象 AgentRuntime 接口，当前 Python runtime 是默认实现。

长期：
当需要复杂工具调用、多 agent 协作、异步队列或可插拔 runtime 时，再评估 pi-agent 作为可选执行面。
```

## 多 Agent 协作触发条件

只有满足下列条件时，才值得拆成多个 agent：

- 任务同时需要生成、审查和证据校验。
- 任务涉及多个信息源，并且来源可能冲突。
- 任务需要专业分工，例如导师画像、学生画像、匹配评分、风险审计。
- 任务失败代价高，例如把错误成绩、论文或导师方向写入正式材料。
- 任务需要长期状态、版本记录和用户确认。

当前最适合保留的链路：

```text
MaterialDraftAgent
-> MaterialReviewAgent
-> EvidenceAuditAgent
```

后续最值得扩展的链路：

```text
AdvisorExtractionAgent
-> MatchAnalysisAgent
-> RiskAuditor
```

以及：

```text
QueryRewriter
-> Retriever
-> Answerer
-> Verifier
```

## 不建议现阶段照搬

| 内容 | 原因 | 本项目取舍 |
| --- | --- | --- |
| MongoDB + Redis 强依赖 | 对本地优先、个人项目部署负担较重 | 先保留 JSON/SQLite 工作区 |
| pi-agent 作为必需服务 | 增加 Node 服务、跨进程通信和调试成本 | 先保持 Python 后端内 Agent 编排 |
| Kubernetes / Helm / HPA | 当前不是生产多租户系统 | 只保留未来规划 |
| PaddleOCR / PaddlePaddle | 依赖重，安装和 CI 成本高 | OCR 作为可选能力 |
| Chroma/Milvus 默认启用 | 小规模知识库不一定需要 | 第一版 BM25 + 元数据过滤 |
| Human-out-of-loop 自动进化 | 申请材料和政策事实风险高 | 反馈生成候选规则，必须用户确认 |
| 复杂部门多 Agent | 本项目不是校园多部门问答 | 抽象成 Profile / Advisor / Material / Knowledge 几类 Agent |

这些能力不是永久排除，而是进入未来有条件路线：MongoDB 对应多用户和复杂查询，Redis 对应长任务队列和缓存，Chroma/向量库对应大规模 RAG，reranker 对应检索质量不足，PaddleOCR 对应扫描件和图片证明材料，K8s 对应多人在线服务和生产部署。

## 推荐落地顺序

1. 保留当前 `MaterialDraftAgent -> MaterialReviewAgent -> EvidenceAuditAgent` 主链路。
2. 做轻量 RAG，先服务学生资料、导师资料和保研常识库。
3. 将 drafter、reviewer、auditor、advisor profiler、deadline checker 转为 portable skill。
4. 增加 10-20 条 RAG/材料生成固定评测样例。
5. 核心工作流完成后，增加 Application Readiness Score / 申请准备度评分，用规则分数评估准备充分度，不预测录取概率。
6. 数据量或任务复杂度明显增加后，再评估 embedding、reranker、外部 Agent runtime、MongoDB、Redis、Chroma、PaddleOCR 和 K8s。

## 参考文件

- 外部项目：`/home/bubble/agent/居丽叶的简历项目9：行政助手Agent/wenshu-project/README.md`
- 外部项目：`docs/architecture.md`
- 外部项目：`docs/loop-engineering.md`
- 外部项目：`docs/change-audit.md`
- 外部项目：`backend/README.md`
- 外部项目：`backend/app/harness/README.md`
- 外部项目：`backend/app/loop/README.md`
- 外部项目：`backend/app/memory/README.md`
- 外部项目：`backend/app/pipeline/README.md`
- 外部项目：`backend/app/retrieval/README.md`
- 外部项目：`web/README.md`
- 外部项目：`services/pi-agent/README.md`
- 外部项目：`deploy/README.md`
