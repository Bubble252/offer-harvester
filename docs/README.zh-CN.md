# Offer Harvester 文档中心

[English](README.md)

这里是持续维护的对外文档入口。本地执行计划和早期规划草稿按设计不进入 Git；历史调研报告用于追溯，不代表当前对外承诺。

## 从这里开始

- [仓库 README](../README.zh-CN.md)：项目范围、限制和本地快速启动。
- [快速开始与 Demo](getting-started.zh-CN.md)：安装、匿名 demo 和本地启动排错。
- [代码架构](architecture.zh-CN.md)：控制面边界、运行模块和数据归属。
- [HTTP API 参考](reference/api.zh-CN.md)：OpenAPI 真相源和稳定接口分组。
- [配置说明](reference/configuration.zh-CN.md)：环境变量、provider 和本地优先默认值。
- [安全与隐私](operations/security.zh-CN.md)：公开边界与 no-send 规则。
- [贡献指南](operations/contributing.zh-CN.md)：开发命令、commit 规范和 PR 流程。
- [发布指南](operations/release.zh-CN.md)：预发布检查、tag 流程和回滚方式。
- [Skills 指南](guides/skills.zh-CN.md)：Portable Skill、产品化 Skill 和 Skill Lab。
- [套磁信教练](guides/skills/contact-email-coach.zh-CN.md)：套磁邮件候选工作流。
- [导师尽调](guides/skills/advisor-due-diligence.zh-CN.md)：基于来源的导师审查。
- [推荐信助手](guides/skills/recommendation-letter-helper.zh-CN.md)：请求与事实素材包工作流。
- [产品化 Skill 独立建库准备度](guides/skills/standalone-readiness.zh-CN.md)：未来独立仓所需的包结构、拆仓清单和校验命令。
- [DeepSeek Harness 指南](guides/deepseek-harness.zh-CN.md)：可选的外部 Agent 适配器。

## 产品参考

- [Demo Walkthrough 记录](11_demo_walkthrough.md)
- [Public KB 与 Agentic RL 基础](18_public_kb_agentic_rl_foundation.md)
- [RAG 与记忆评测报告](16_rag_memory_evaluation_report.md)
- [本地模型运行时](17_local_model_runtime.md)

## 贡献者参考

- [Contributing](../CONTRIBUTING.md) | [中文](../CONTRIBUTING.zh-CN.md)
- [Security](../SECURITY.md) | [中文](../SECURITY.zh-CN.md)
- [CHANGELOG](../CHANGELOG.md) | [中文](../CHANGELOG.zh-CN.md)
- [参考项目差距审查](13_reference_project_gap_audit.md)

FastAPI 的 `/docs` 和 `/openapi.json` 是 HTTP 契约的真相源。Markdown 解释使用方式和边界，但不覆盖运行中的 OpenAPI schema。
