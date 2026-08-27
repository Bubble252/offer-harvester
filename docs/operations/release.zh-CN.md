# 发布指南

[English](release.md)

## 版本策略

仓库仍处于 `0.y.z` 阶段，遵循语义化版本：

- patch：兼容性 bug 或文档修复
- minor：新增用户能力
- major：留给 MVP 之后的兼容性契约
- `-rc.N`：需要人工验收的预发布候选

当前公开候选版本为 `0.2.0-rc.1`，不是稳定的 `v1.0.0`。

## 发布门禁

打 tag 或发布前运行：

```bash
make verify
```

同时完成：

- 浏览器打开空白应用和匿名合成 Demo。
- 检查 `/docs`、`/openapi.json`、Skill Lab 和 DSH 配置示例。
- 确认没有真实资料、secret、私有路径、超大二进制或外部源码树被跟踪。
- 确认 README、中英文 CHANGELOG、截图和公开文档对已实现能力描述一致。
- 记录已知限制和迁移说明。

## 预发布流程

1. 更新 `pyproject.toml`、`CHANGELOG.md`、`CHANGELOG.zh-CN.md` 和公开文档。
2. 运行 `make verify`，完成手动 Demo 验收。
3. 创建包含背景、变更、验证和边界的 release commit。
4. 推送 feature 分支并审查 PR。
5. 合并后在合并提交上创建带说明的 tag，例如 `v0.2.0-rc.1`。
6. 使用 `.github/release.yml` 发布 GitHub Release notes。

除非对应产物真实存在且可复现，否则不要添加 downloads、Docker、PyPI、npm 或 benchmark
徽章。

## 回滚

优先创建新的修复 commit。如果候选版本存在安全问题，将 GitHub Release 标为 pre-release，
记录问题、停用受影响的可选集成，并发布修正版候选。不要强制推送公共分支。
