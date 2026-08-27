# 贡献指南

[English](contributing.md)

## 开发循环

1. 检查当前分支和工作区。
2. 阅读相关公开指南和源码模块。
3. 在所属模块内修改，并保持证据与隐私边界。
4. 增加聚焦测试；用户可见行为同时更新中英文公开文档。
5. 运行 `make verify`。
6. 创建清晰的 Conventional Commit，并发起 PR。

## 常用命令

```bash
make install
make run
make seed-demo
make verify
```

本地运行时显式使用 `WORKSPACE_DIR` 或 `workspace.demo`。不要在截图和测试中使用真实
学生 workspace。

## 架构规则

- Python FastAPI 继续作为控制面。
- Skill 和外部 runtime 通过稳定 adapter 调用，不能绕过存储或 EvidenceAudit。
- 新的 candidate 生成行为默认必须是 `no_send`。
- 新增公开 API 时必须同时有 Pydantic 模型、OpenAPI 分类/summary、契约测试、中英文
  文档和 changelog 条目。
- 重型依赖应放在 optional extra 或 adapter 边界后，并提供 fallback。

## Pull Request

使用仓库 PR 模板，说明 What、Why、How、Testing、Privacy and Boundaries 以及 Rollback。
不要把无关重构混入功能 commit，不要改写已经推送的公共历史。

## Commit 格式

```text
feat(scope): concise result
```

涉及行为、隐私、数据模型或集成时，正文必须包含：

```text
背景：
- 为什么需要此变更。

变更：
- 修改了什么、位于哪里。

验证：
- 执行了哪些命令和手动检查。

边界：
- 隐私、fallback、兼容性和已知限制。
```

## 新增 Skill 检查

- 定义一个边界清晰的用户任务。
- 增加 `SKILL.md`、references、schema/fixture 和有价值的确定性校验。
- 在 catalog 增加 `no_send` 和写权限。
- 产品化 Skill 使用受控 adapter。
- 输入输出和安全边界稳定后再增加 UI。
