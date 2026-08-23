# 医疗助手项目参考总结

本文档整理 `/home/bubble/agent/居丽叶简历项目7：医疗助手` 中值得借鉴的设计，并明确哪些部分适合迁移到 `grad-apply-workflow`，哪些不建议直接照搬。

## 项目定位

这个项目不是单纯的问答机器人，而是一个“技能层 + Agent 编排层 + 记忆层 + 约束层”的完整系统：

- `Skills` 负责最小原子能力
- `AgentLoop` 负责多轮工具调用
- `SwarmCoordinator` 负责简单/复杂任务路由
- `LeadAgent` 负责任务拆解
- `SharedContext` 和事件系统负责多 agent 协作
- `Memory`、`KB`、`Constraint`、`AutoFixer` 负责长期运行质量

## 值得借鉴的点

### 1. Skills 作为稳定接口

它把能力拆成多个可注册 skill，再统一转成 function calling schema。这个思路适合我们后续做：

- `drafter`
- `reviewer`
- `auditor`
- `advisor`
- `match`
- `ppt`
- `connector`

好处是：

- 每个能力边界清晰
- 便于测试和替换
- 适合做 portable skill

### 2. AgentLoop 的执行模型

它的核心不是“一个大 prompt”，而是：

`LLM -> tool call -> observe -> repeat`

这对我们很有价值，尤其适合：

- 材料草稿生成
- 证据补全
- 导师分析
- PPT 单页修改

### 3. SharedContext + Event 驱动协作

它把多 agent 协作做成共享上下文和事件流，而不是互相硬调用。

适合我们借鉴的地方：

- 任务拆解记录
- 子 agent 贡献记录
- 审计链路
- 可回放的工作流事件

### 4. 分层记忆

它把记忆分成：

- short-term memory
- long-term memory
- session summary
- entropy cleanup

这比“一个 history 列表”更稳。对我们来说，至少应该保留：

- 原始用户资料
- 结构化 profile
- 会话摘要
- 任务事件
- 申请/材料历史

### 5. 约束和自动修复

`ConstraintValidator` + `AutoFixer` 这套很实用：

- 先校验再输出
- 高风险内容加 warning
- 超长内容自动截断

这和我们现在的 evidence gate、quality report、confirmed/unconfirmed 规则是同一类思路。

### 6. 深度检索流程

它的 research workflow 值得借鉴：

- 先拆 query
- 并行检索
- 再做 evidence synthesis
- 最后根据冲突情况补检

对我们后续的 RAG、导师调研、保研政策说明都适用。

### 7. 评测和基准意识

这个项目很重视 tests、examples、benchmark 和 workflow 验证。我们也应该保持：

- 固定测试集
- 回归测试
- demo walkthrough
- 质量报告

### 8. 自我进化与 RL 边界

医疗助手项目中的“自我进化”需要拆成两层理解：

- 工作流层：根据失败案例、审核结果和用户反馈更新 skill、hook、rule、strategy 或实验版本。
- 参数训练层：使用 reward、rollout 和训练框架更新模型权重。

前者是该项目更适合本项目近期借鉴的部分；后者主要出现在其 `MediX-R1` 训练目录中，属于重型、多 GPU、分布式 RL 基础设施。它们不是同一件事。

可借鉴：

- 保存 Agent 运行、审计问题、用户修改和任务结果。
- 把反馈转换成待审核的 skill/rule/prompt 候选。
- 将规则评测、LLM Judge、embedding 相似度和格式检查拆成独立 reward/eval 组件。
- 将训练数据、reward、judge、baseline 和实验版本分离管理。

不直接迁移：

- 医疗领域的 reward、ground truth、免责声明和训练数据。
- `MediX-R1` 的 Ray、veRL、vLLM、FSDP、GPU rollout 和模型权重。
- 任何自动修改本项目核心事实规则或绕过 EvidenceAudit 的“自我进化”。

对本项目的落点：

```text
WorkflowEvent / AgentRun / UserEdit
-> feedback memory
-> reward/evaluation record
-> skill/rule/prompt candidate
-> human approval
-> versioned strategy
```

RL 训练只有在匿名数据、离线评测和 baseline 对比稳定后才考虑；当前优先建设数据记录和评测接口。

## 不建议直接照搬的点

### 1. 医疗场景 prompt 和免责声明

这些是医疗特定内容，不适合直接迁移。

### 2. 重型训练栈

`MediX-R1` 里的 RL、Ray、vLLM、重训练/eval 体系，更适合作为远期能力，不应作为当前 MVP 依赖。

### 3. 把多个存储/检索组件一次性全上

它用了 Mem0、Milvus Lite、知识库、长期记忆等多层实现。我们可以借鉴结构，但不应一开始就同时引入多套重依赖。

### 4. 过早做成“很多 agent”

医疗项目里 agent 数量多，但我们当前阶段更适合：

- 先把控制面收口
- 先保证 evidence / profile / review 主链路稳定
- 再逐步挂子 agent

## 对我们项目的映射

### 已有基础

我们现在已经具备一个总控制器雏形：

- `app/backend/` 控制面
- `app/backend/agents/` 工作流编排
- `WorkflowEvent` / `AgentRun`
- `MaterialDraftAgent -> MaterialReviewAgent -> EvidenceAuditAgent`

### 适合继续补的能力

- skills registry / portable skill
- shared context / event log
- session summary / long-term profile memory
- constraints / auto-fix
- research / evidence synthesis
- fixed test set + workflow regression

### 适合后置的能力

- 更复杂的多 agent swarm
- 外部 runtime 插件化
- 重型向量库和训练栈
- 复杂的自我进化体系

## 结论

医疗助手项目最值得借的是“工程化的 agent 组织方式”，而不是具体医疗业务本身。

对我们来说，最有价值的落点是：

1. 先把 skill 化、事件化、记忆分层、约束校验做扎实
2. 再把 research / RAG / evidence synthesis 接进主链路
3. 最后才考虑更复杂的 swarm、pi-agent、训练和自我进化
