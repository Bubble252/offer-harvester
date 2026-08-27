# Contributing

[简体中文](CONTRIBUTING.zh-CN.md)

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
ruff check .
ruff format --check .
python tools/security_guards.py
python tools/lint_docs.py
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

## 工程守卫

本项目默认使用 `pyproject.toml` 维护 pytest 和 ruff 配置。新增 Python 代码后应保持以下检查通过：

```bash
ruff check .
ruff format --check .
pytest -q
```

`tools/security_guards.py` 是仓库级安全检查，用于阻止以下内容进入 Git：

- `.env`、API key、私钥和证书文件
- `workspace/`、真实用户资料、生成运行目录
- 外部参考项目整目录或明显复制体
- 缺少 `NOTICE` 中的外部项目引用边界

`tools/lint_docs.py` 用于做轻量文档一致性检查。修改 MVP 范围、数据对象、Agent 阶段、PPTAgent 边界或工作区目录时，应同步更新 `docs/`。

## Release checklist

发布前需要完成：

```bash
ruff check app tests
ruff format --check app tests
pytest -q
node --check app/frontend/app.js
python -m compileall -q app integrations tests
python tools/lint_docs.py
python tools/security_guards.py
git diff --check
```

同时检查：

- README 首屏说明项目定位、quickstart、隐私边界和 optional integrations
- CHANGELOG 按版本号和日期整理
- Demo walkthrough 截图和文字与当前 UI 对齐
- GitHub Release notes 使用 `.github/release.yml` 分组
- 不添加不存在的 PyPI、npm、Docker、downloads 或 citation badge

## Documentation language policy

- `README.md` is the English entry point for GitHub visitors and releases.
- `README.zh-CN.md` is the full Simplified Chinese entry point for the primary user audience.
- Keep both README files aligned on implemented features, privacy boundaries, optional integrations, and quickstart commands.
- `CHANGELOG.md` stays English-first so GitHub release notes can reuse it directly.
- Internal planning docs do not need to be bilingual unless they become public user-facing guides.
