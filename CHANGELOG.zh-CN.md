# 变更记录

[English](CHANGELOG.md)

所有重要变更都记录在这里。版本遵循语义化版本的 `0.y.z` MVP 阶段规则，因此 `1.0.0`
之前的公开 API 仍可能调整。

## [未发布]

### 计划中

- 在粘贴邮件信号链路稳定后接入可选的 Gmail / QQ OAuth。
- 通过 `PptAgentAdapter` 接入可选的真实 PPTAgent runtime。
- 在隐私规则确定后接入 Notion / 飞书等外部看板单向写入。

## [0.2.0-rc.1] - 2026-08-27

### 新增

- Offer Harvester 对外文档中心，以及中英文快速开始、架构、API、配置、安全、贡献和发布指南。
- 预发布版本元数据、Makefile 命令、OpenAPI 分类、API 契约检查、公开边界检查和 GitHub 协作模板。
- Skill Lab 文档与 DeepSeek Harness 接入指南，明确 scoped token 和 no-send 边界。
- 为 GitHub README 和本地导航优化的新项目 Logo 资产。

### 调整

- 对外产品名和 API 标题从 Grad Apply Workflow 统一为 Offer Harvester。
- 当前版本定位为 `0.2.0-rc.1`，不承诺已经是稳定 `v1.0.0`。
- 支持的公开文档统一进入文档中心，历史规划/调研报告不再位于主导航。

### 安全

- release 检查会拒绝支持文档中常见的 secret 和私有绝对路径泄露。
- 外部 Agent 工具继续保持 candidate-only、no-send，且不能直接写入 confirmed profile、最终材料、tracker 或 memory promotion 状态。

### 已知限制

- 默认应用仍为本地优先，不包含真实 OAuth 同步、外部 PPTAgent runtime、Redis Worker 或已发布的 DSH package。
- 本次预发布的浏览器工作台仍以中文优先；公开文档保持中英文对等。

## [0.1.0] - 2026-08-23

完整 `0.1.0` 英文变更记录见 [CHANGELOG.md](CHANGELOG.md)。后续版本开始将保持两个版本文件同步更新。
