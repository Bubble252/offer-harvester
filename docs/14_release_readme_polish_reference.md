# README / Release Polish Reference

本文件用于 release polish 前的开源文档规范检查。目标不是照搬大项目 README，而是提炼适合本项目当前阶段的结构、徽章和发布流程。

## 调研对象

参考对象选择 GitHub 上成熟、使用广、引用多或生态影响力强的项目：

- Hugging Face Transformers: https://github.com/huggingface/transformers
- LangChain: https://github.com/langchain-ai/langchain
- FastAPI: https://github.com/fastapi/fastapi
- vLLM: https://github.com/vllm-project/vllm
- pandas: https://github.com/pandas-dev/pandas
- Keep a Changelog: https://keepachangelog.com/en/1.1.0/
- Semantic Versioning: https://semver.org/
- GitHub automatically generated release notes: https://docs.github.com/en/repositories/releasing-projects-on-github/automatically-generated-release-notes
- Diataxis documentation framework: https://diataxis.fr/

## 成熟 README 的共同结构

高成熟项目通常先解决四个问题：

1. 这是什么
2. 谁应该用
3. 如何最快跑起来
4. 去哪里看完整文档、贡献和发布记录

常见结构：

```text
Logo / 项目名
Badges
一句话定位
适用场景 / 核心能力
Quickstart
Documentation / Tutorials
Examples / Demo
Installation
Project structure 或 Architecture
Configuration
Security / Privacy
Contributing
Citation / Acknowledgements
License
```

不同项目侧重点：

- Transformers：强调一句话定位、安装、quickstart、何时适合/不适合使用、多语言入口和生态链接。
- LangChain：强调 agent / LLM 应用定位、quickstart、生态组件、资源入口和贡献入口。
- FastAPI：强调文档入口、核心特性、安装、最小示例和自动 API docs。
- vLLM：强调支持范围、getting started、文档、贡献和 citation。
- pandas：强调 badges 分组、what is it、目录、安装渠道、文档、帮助渠道、讨论开发和贡献。

## Badges 规范

Badges 只展示真实、可验证、不会误导用户的信息。

第一版建议使用：

- CI: GitHub Actions 状态
- License: MIT
- Python: 当前支持版本
- Release: GitHub release version，发布后再启用
- Privacy: local-first / workspace ignored，使用静态 badge 即可

暂不建议使用：

- PyPI version：项目尚未发布 PyPI 包
- npm version：项目没有 npm 包
- Downloads：没有真实包下载量，不应伪造
- Docker pulls：没有 Docker 镜像
- Coverage：没有稳定 coverage 上传链路
- Citation count：项目没有论文或 DOI

如果未来发布包：

- Python 包发布后再加 PyPI version 和 PyPI downloads
- Docker 镜像发布后再加 image version 和 pulls
- 有论文 / DOI 后再加 citation / DOI badge

## README 适配本项目的推荐结构

语言规则：

- `README.md` 是英文主版，面向 GitHub 外部用户、搜索结果、PR 和 Release 页面。
- `README.zh-CN.md` 是完整中文主版，面向实际保研 / 硕博申请用户。
- 两个 README 顶部必须互相链接。
- 两个 README 的能力边界、隐私声明、optional integrations 和 quickstart 必须保持一致。
- CHANGELOG 默认英文为主，便于 GitHub Release notes 复用。
- Demo walkthrough 可以中文优先，后续如果有英文用户再补 `docs/11_demo_walkthrough.en.md`。
- `docs/01_*.md` 到 `docs/09_*.md` 等内部规划文档不强制双语。

```text
# Grad Apply Workflow / Offer Harvester

Logo
Badges
一句话定位

## What It Does
用 5-7 个 bullet 讲真实能力，不写未来未实现功能。

## Why This Exists
强调保研 / 硕博申请的证据、隐私、人工确认和可审计工作流。

## Quickstart
从 clean clone 到打开网页的最短命令。

## Demo
链接 docs/11_demo_walkthrough.md 和截图。

## Core Workflow
学生资料 -> 导师来源 -> 目标 -> 匹配 -> 材料 -> 审核 -> PPT -> tracker。

## Features
按已实现能力分组：Profile、Advisor、Materials、RAG、Lifecycle、Presentation。

## Data And Privacy
说明 workspace/、.env、用户资料、邮件正文和网页来源的边界。

## Optional Integrations
LLM provider、PPTAgent adapter、邮箱/外部看板、RAG 扩展都标为 optional。

## Documentation
列出 demo、schema、open-source readiness、reference audit 等文档入口。

## Development
测试、ruff、node check、security guards。

## Release Notes
链接 CHANGELOG.md 和 GitHub Releases。

## Contributing / Security / License / Acknowledgements
```

## 教程与文档规范

采用 Diataxis 的四分法，但保持轻量：

- Tutorial：从零跑通 demo。对应 `docs/11_demo_walkthrough.md`
- How-to：如何导入学生资料、添加导师、生成材料、上传参考 PPT、导入邮件信号
- Reference：数据 schema、API、workspace 目录、环境变量
- Explanation：设计边界、参考项目借鉴、隐私与安全、RAG/Agent/PPTAgent 规划

当前 release polish 应补齐的最小文档：

- README: 作为入口页
- CHANGELOG: 面向用户的版本变化
- docs/11_demo_walkthrough.md: 截图式教程
- docs/10_open_source_readiness.md: 开源合规说明
- SECURITY.md: 隐私和安全边界
- CONTRIBUTING.md: 开发者入口

后续可新增：

- docs/how_to_use.md
- docs/api_reference.md
- docs/workspace_reference.md

## Changelog 规范

采用 Keep a Changelog 的结构：

```text
# Changelog

## [Unreleased]

### Added
### Changed
### Fixed
### Security

## [0.1.0] - YYYY-MM-DD
```

规则：

- 不把 git log 直接当 changelog
- 只写用户或开发者需要知道的变化
- 最新版本放在最上方
- 版本号和日期必须明确
- 安全、隐私、破坏性变更单独列出

## 版本号规范

采用 SemVer。

当前项目仍处于初始开发期，适合发布：

- `v0.1.0`: 第一个可演示 MVP
- 后续小修复：`v0.1.1`
- 新增兼容功能：`v0.2.0`
- 公开 API 稳定后再考虑 `v1.0.0`

约束：

- `0.y.z` 阶段可以变动，但 README 必须明确“不承诺稳定公共 API”
- 每次 GitHub Release 对应一个 tag
- 已发布 tag 不改写，修复用新版本

## GitHub Release 工作流

建议流程：

1. 确认 `main` 是干净状态
2. 跑全量验证
3. 更新 README / CHANGELOG / demo walkthrough
4. 打 tag，例如 `v0.1.0`
5. 在 GitHub Releases 中生成 release notes
6. 人工检查自动生成内容，补上用户可读摘要、边界和验证命令
7. 发布 release

本项目已加入 `.github/release.yml`，用于给 GitHub 自动 release notes 分组。

## Release Polish 前检查清单

- [ ] README 首屏能说明项目是什么、适合谁、当前能做什么
- [ ] README 不承诺未实现的真实邮箱 OAuth、真实外部看板写入、PPTAgent runtime
- [ ] README badges 只使用真实状态，不展示虚假的下载量或包版本
- [ ] Quickstart 在 clean clone 下可执行
- [ ] Demo walkthrough 截图与当前 UI 对齐
- [ ] CHANGELOG 使用 `Unreleased` 和 `0.1.0` 结构
- [ ] SECURITY 明确 workspace、.env、邮件正文、学生资料不会进 Git
- [ ] CONTRIBUTING 包含测试、ruff、security guard 和 commit message 规范
- [ ] GitHub release notes 配置存在
- [ ] 全量验证命令通过

## 对当前项目的直接结论

当前 release polish 前应先做 README 结构升级，而不是先追求下载量、版本号徽章或复杂官网。

适合马上加的：

- CI / License / Python / Local-first badges
- 更清楚的 Quickstart
- Demo workflow 和截图入口
- 已实现功能矩阵
- 隐私和人工确认边界
- Optional integrations 边界
- Release / Changelog 入口

暂缓：

- 下载量 badge
- PyPI / npm badge
- Docker badge
- Citation badge
- 复杂文档站
