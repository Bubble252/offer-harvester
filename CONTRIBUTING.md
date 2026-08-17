# Contributing

Keep the project focused on the Chinese MVP for recommendation-based graduate applications.

## Development

```bash
cd app/backend
python -m pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## Rules

- Do not commit `workspace/`.
- Do not commit API keys.
- Do not copy external project directories into this repository.
- Use neutral names such as `workflow_engine` and `presentation_engine` for adapters.
- Keep comments concise: explain intent, edge cases, evidence boundaries, and privacy risks.
- Write comments in the language of the surrounding module and explain why, constraints,
  fallback behavior, or audit requirements. Do not restate obvious code behavior.
- Do not copy external comments or paste research notes into production code; record those
  details in `docs/` and update `NOTICE` if a third-party component is actually reused.

## Git 提交与推送

每个可识别的逻辑任务都必须有对应 commit。一个逻辑任务可以包含代码、测试和必要文档，但不得把无关改动混入同一个 commit。

提交前至少执行：

```bash
git status --short
git diff --check
pytest -q
```

涉及前端或多模块代码时，额外执行：

```bash
node --check app/frontend/app.js
python -m compileall -q app integrations tests
```

只暂存本次任务涉及的文件，并检查暂存区：

```bash
git add <本次任务涉及的文件>
git diff --cached --check
git diff --cached
git commit -m "feat(scope): 简洁说明本次变更"
git log -1 --stat
git status --short
git push origin <当前分支>
```

Commit 标题采用 Conventional Commits：

```text
feat(advisor): 增加导师信息手动粘贴兜底
fix(material): 阻止缺少来源的结论进入报告
docs(repo): 更新开源提交规范
test(presentation): 增加 PPTX 生成适配器测试
```

涉及业务逻辑、隐私、安全、数据结构或外部适配器时，commit 正文还应记录背景、主要变更、验证命令和已知边界。禁止提交 `workspace/`、`.env`、API key、真实学生材料、导师私人信息、临时生成文件或外部项目源码副本。已经推送的公共 commit 不使用强制推送改写历史，修复请创建新的 commit。
