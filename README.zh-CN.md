# Offer Harvester

[English](README.md) | 简体中文

<p align="center">
  <img src="app/frontend/assets/logo.png" alt="Offer Harvester logo" width="180" />
</p>

<p align="center">
  <a href="https://github.com/Bubble252/offer-harvester/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/Bubble252/offer-harvester/actions/workflows/ci.yml/badge.svg" /></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-blue" />
  <img alt="License" src="https://img.shields.io/badge/license-MIT-green" />
  <img alt="Local first" src="https://img.shields.io/badge/data-local--first-2f855a" />
</p>

Grad Apply Workflow 是一个本地优先的保研 / 硕博申请 Web 工作台。它帮助学生把真实个人资料和公开导师来源转化为可审计的目标调研、匹配分析、中文申请材料、面试准备、可编辑 PPTX 和申请状态追踪。

当前项目处于 MVP 阶段。它不预测录取概率，不自动发送邮件，也不能替代用户复核。

## 当前能做什么

- 保存本地学生资料，并抽取带字段级证据的结构化画像。
- 从公开 URL 或手动粘贴文本中采集导师、实验室和招生信息。
- 创建申请目标，跟踪状态、截止日期、备注、归档和 outcome。
- 生成匹配分析、套磁邮件草稿、面试问题和 PPT 大纲。
- 运行 `drafter -> reviewer -> evidence auditor` 材料工作流，并输出质量报告。
- 使用本地兜底 adapter 生成可编辑 16:9 PPTX。
- 对学生资料、导师来源、生成材料和政策知识做轻量 RAG 检索。
- 从粘贴邮件文本中识别导师回复、面试、补材料、拒信、offer、waitlist 等候选信号，并且只在用户确认后写入 tracker。
- 提供 Skill Lab，包含套磁信教练、导师尽调、推荐信素材包三个可审阅且 no-send 的产品化 Skill。

## 快速开始

```bash
git clone https://github.com/Bubble252/offer-harvester.git
cd offer-harvester
python -m pip install -r app/backend/requirements.txt
cd app/backend
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

打开：

```text
http://127.0.0.1:8000
```

如需使用匿名 demo 数据：

```bash
cd app/backend
WORKSPACE_DIR=/path/to/offer-harvester/workspace.demo uvicorn main:app --host 127.0.0.1 --port 8000
```

## Demo

截图式教程见：[docs/11_demo_walkthrough.md](docs/11_demo_walkthrough.md)

核心流程：

```text
学生资料
-> 字段证据和确认状态
-> 导师公开来源
-> 申请目标
-> 匹配分析
-> 审核后的套磁邮件
-> 面试问题和 PPTX
-> 生命周期 tracker 和邮件信号
```

## 文档入口

- [文档中心](docs/README.zh-CN.md)
- [Skills 指南](docs/guides/skills.zh-CN.md)
- [DeepSeek Harness 指南](docs/guides/deepseek-harness.zh-CN.md)
- [Demo Walkthrough](docs/11_demo_walkthrough.md)
- [Open Source Readiness](docs/10_open_source_readiness.md)
- [Release README Polish Reference](docs/14_release_readme_polish_reference.md)
- [Reference Project Gap Audit](docs/13_reference_project_gap_audit.md)
- [Wenshu Agent Reference](docs/12_wenshu_agent_reference.md)
- [NOTICE](NOTICE)
- [CONTRIBUTING](CONTRIBUTING.md)
- [SECURITY](SECURITY.md)
- [CHANGELOG](CHANGELOG.md)

`docs/01_*.md` 到 `docs/09_*.md` 属于早期本地规划草稿，默认被 Git 忽略。

## 数据与隐私

真实学生资料、导师联系记录、生成草稿、申请归档、RAG 索引和粘贴邮件文本都应保存在 `workspace/` 中。该目录默认不会进入 Git。

不要提交：

- `.env` 或 API key
- 真实简历、成绩单、推荐信、证书
- 真实套磁邮件或邮箱导出
- 真实用户生成材料
- 外部参考项目源码目录复制体

所有生成材料都只是草稿。用户必须自行核对事实，并自行决定是否发送。

## 可选集成边界

MVP 不依赖外部 LLM 或重模型依赖即可运行。

以下能力都作为可选或未来能力保留在 adapter 边界后：

- OpenAI-compatible LLM provider，用于增强抽取或生成。
- PPTAgent runtime，用于未来参考模板学习和高级单页编辑。
- Vision / OCR provider，用于未来扫描件或 PPT 视觉检查。
- Gmail / QQ OAuth、Notion / 飞书同步，用于未来真实外部集成。
- DeepSeek Harness 是可选的外部 Agent adapter，只调用受控 candidate API，不是运行主应用的必需依赖。
- MongoDB、Redis、Chroma、reranker、PaddleOCR、K8s 等基础设施，只在本地文件方案达到限制后评估。

默认代码路径不依赖 `torch`、ViT 权重、`oaib`、外部 PPTAgent 源码树或云数据库。

## 开发

提交 PR 前建议运行：

```bash
ruff check app tests
ruff format --check app tests
pytest -q
node --check app/frontend/app.js
python -m compileall -q app integrations tests
python tools/lint_docs.py
python tools/security_guards.py
```

项目采用 Conventional Commits。涉及功能、隐私、数据模型或外部集成时，commit 正文应写清背景、变更、验证和边界。

## Release Notes

变更记录见 [CHANGELOG.md](CHANGELOG.md)。GitHub Release notes 使用 [.github/release.yml](.github/release.yml) 做分组。

第一个 MVP release 计划为 `v0.1.0`。

## License

MIT. 见 [LICENSE](LICENSE)。

## 致谢与参考边界

参考项目与借鉴边界记录在 [NOTICE](NOTICE)、[docs/13_reference_project_gap_audit.md](docs/13_reference_project_gap_audit.md) 和 [docs/14_release_readme_polish_reference.md](docs/14_release_readme_polish_reference.md)。本仓库保留自有实现和中性 adapter 命名，不复制外部项目源码树。
