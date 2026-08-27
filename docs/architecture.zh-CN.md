# 代码架构

[English](architecture.md)

## 系统边界

Offer Harvester 是本地优先的控制面。浏览器、外部 Agent、可选 provider 和未来的
worker 都是客户端或适配器，不能成为事实真源。

```text
浏览器 / Skill Lab / 可选 DSH 插件
                  |
                  v
            FastAPI 控制面
                  |
      +-----------+-----------+
      |           |           |
   Agent 工作流  RAG+证据    记忆+反馈
      |           |           |
      +-----------+-----------+
                  |
           本地 workspace 存储
```

控制面负责：

- 学生画像和原始文件落盘
- 字段级确认状态
- 导师和政策证据
- 候选材料生命周期
- EvidenceAudit 和质量门禁
- 记忆 promotion 决策
- 申请 tracker 和用户确认后的状态变更
- 隐私路由和 no-send 行为

## 模块地图

| 区域 | 路径 | 职责 |
| --- | --- | --- |
| API 与控制面 | `app/backend/main.py` | FastAPI 路由、依赖装配、OpenAPI |
| 领域模型 | `app/backend/models.py` | Pydantic 数据和请求/响应结构 |
| Workspace | `app/backend/storage.py` | 本地 JSON/文件持久化和 manifest |
| Agent 工作流 | `app/backend/agents/` | 草稿、审查、审计、导师、匹配和 SWARM 协议 |
| RAG | `app/backend/rag/` | 切块、embedding、检索、重排和证据包 |
| 记忆 | `app/backend/memory.py` | 分层记忆生命周期和 promotion candidate |
| 质量 | `app/backend/quality/` | 材料检查和风险发现 |
| Skills | `skills/`、`app/backend/skill_*.py` | portable 契约、产品适配器和 Skill Lab |
| 集成 | `integrations/` | 中性适配器和可选外部 runtime |
| 前端 | `app/frontend/` | 本地浏览器工作台和产品 Skill UI |
| 工具 | `tools/` | Demo、评测、lint、安全和发布检查 |

## 请求生命周期

```text
前端或适配器请求
-> FastAPI 请求模型
-> 领域服务 / Agent 工作流
-> 按需进入 RAG 和 EvidenceBundle
-> reviewer 与 EvidenceAudit
-> candidate 结果 + trace
-> 用户确认
-> 受控 workspace 写入
```

适配器可以请求 candidate 或报告，但不能直接 import 存储内部实现去修改 confirmed
profile、tracker、最终材料、公开知识或已 promotion 的记忆。

## Agent 边界

核心材料链路为：

```text
MaterialDraftAgent -> MaterialReviewAgent -> EvidenceAuditAgent
```

SWARM 用于有独立证据切片的受控并行任务，例如导师来源抽取和检索评测。不能为了
“看起来像多智能体”而拆分简单 CRUD 或字段更新。未来的 pi-agent 或 DeepSeek Harness
runtime 可以通过适配器执行局部任务，但 Python 仍是总编排器。

## 数据归属

- `workspace/` 是用户数据和运行记录的本地事实源。
- `workspace.example/` 和 `workspace.demo/` 只放合成示例。
- 公开知识记录保留来源元数据、时间、hash、有效期和证据引用；历史或未确认信息
  不会被静默提升。
- Markdown、HTML、PPTX 和报告都是派生视图，不能覆盖结构化状态。

## 可选重型组件

默认栈使用本地文件、确定性 fallback 和轻量适配器。SQLite/FTS、Chroma、Milvus、
Redis、MongoDB、PaddleOCR、本地 PyTorch 模型、ViT、vLLM 和 Kubernetes 都保持可替换。
任何重型组件都必须保留证据引用、隐私路由、取消能力、失败 fallback 和用户确认。
