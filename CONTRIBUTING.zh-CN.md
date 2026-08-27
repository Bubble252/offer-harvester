# 贡献指南

[English](CONTRIBUTING.md)

## 开发环境

项目是本地优先的 FastAPI + 静态前端应用。建议使用 Python 3.11 或更高版本：

```bash
python -m venv .venv
. .venv/bin/activate
make install
make run
```

匿名演示数据使用：

```bash
make run-demo
```

## 目录边界

- `app/backend/`：主控制面、Agent 工作流、RAG、记忆和 API。
- `app/frontend/`：当前中文优先的本地工作台与 Skill Lab。
- `skills/`：portable 协议与产品化 Skill 的 canonical 文件。
- `integrations/`：受控外部运行时适配器，例如 DeepSeek Harness。
- `workspace/`：真实本地资料和运行数据，永远不提交。
- `workspace.example/`：匿名结构示例，可提交。
- `docs/`：公开说明和历史参考；本地执行计划由 `.gitignore` 排除。

## 提交前验证

```bash
make verify
```

如果修改了浏览器交互，还要进行一次本地页面 smoke test。修改 API 时要检查
`/docs` 和 `/openapi.json`，并为新的稳定行为增加契约测试。

## 代码与隐私规则

- 一个 commit 只解决一个可识别的逻辑任务。
- 不提交 `.env`、API key、真实学生资料、真实邮箱正文、生成材料或外部项目源码。
- 新的 Skill 默认 `no_send`，输出只能是 candidate，不能绕过 EvidenceAudit、用户确认或隐私路由。
- 公开来源必须尊重 robots、ToS、访问限制和最小化保存原则。
- 外部依赖应放在 adapter 后，并提供明确的 fallback 或禁用方式。

## Commit、PR 与发布

使用 Conventional Commits，例如：

```text
feat(skill): 增加可审阅的导师尽调 Skill
fix(rag): 阻止过期政策进入当前建议
docs(repo): 更新双语 API 指南
```

涉及业务、安全、数据模型或外部适配器时，正文写清背景、变更、验证和边界。
PR 使用仓库模板，并说明回滚方式。预发布版本必须遵循
[发布指南](release.zh-CN.md)。
