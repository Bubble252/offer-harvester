# 开源项目化规划

## 目标

本项目最终应整理成一个标准 GitHub 开源项目，而不是只在本地保存规划文档或实验代码。

开源化目标：

- 让新用户能快速理解项目用途
- 让开发者能按文档启动后端和前端
- 避免提交真实学生隐私数据
- 避免复制外部参考项目源码
- 最终代码目录、包名、测试名和 API 命名避免直接出现参考项目原名
- 文档中允许明确说明参考项目、参考模块和借鉴点
- 清楚说明项目边界、许可证、贡献方式和安全注意事项

## 推荐根目录结构

```text
grad-apply-workflow/
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
├── CHANGELOG.md
├── .gitignore
├── .env.example
├── docs/
├── .agents/
│   └── skills/
├── app/
│   ├── backend/
│   └── frontend/
├── integrations/
│   ├── workflow_engine/
│   └── presentation_engine/
├── workspace.example/
├── tests/
├── tools/
└── .github/
    └── workflows/
        └── ci.yml
```

说明：

- `workspace/` 用于本地真实用户数据，必须加入 `.gitignore`
- `workspace.example/` 用于匿名样例数据，可以进入 Git
- `.agents/skills/` 用于项目内 portable skill 协议，不放真实用户资料或运行产物
- `integrations/` 只放本项目自有适配器，不放外部项目复制体
- `workflow_engine/` 和 `presentation_engine/` 是中性命名，不是外部项目副本
- `docs/` 保存产品、技术、执行计划和 schema 文档

## 必需文件

### README.md

README 需要优先讲用户场景，而不是先讲模型。

建议结构：

```text
# Grad Apply Workflow

一句话介绍
适用人群
核心功能
Demo 流程
快速开始
项目结构
配置说明
隐私与安全
路线图
许可证
致谢与参考项目
```

核心定位建议：

> 面向保研硕博申请的 AI 工作台，帮助学生基于真实导师信息完成稳妥型导师匹配、申请材料定制、套磁邮件、面试准备和展示材料生成。

### LICENSE

推荐选择：

- MIT：简单宽松，适合早期项目
- Apache-2.0：更正式，包含专利授权条款

第一版如果没有商业化约束，建议使用 MIT。

### .gitignore

必须忽略：

```text
.env
workspace/
__pycache__/
.pytest_cache/
node_modules/
dist/
runs/
*.log
*.key
```

特别注意：

- `workspace/` 可能包含简历、成绩单、套磁邮件、导师记录，不能提交
- API key 和模型配置不能提交
- 演示文稿生成产生的临时 runs 目录不能提交

### .env.example

只放示例变量，不放真实 key。

示例：

```bash
APP_ENV=development
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
FRONTEND_PORT=5173

LLM_PROVIDER=openai
OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_MODEL=

HTTP_PROXY=
HTTPS_PROXY=

PRESENTATION_ENGINE_ROOT=
WORKSPACE_DIR=./workspace
```

### SECURITY.md

需要明确：

- 不要提交真实学生材料
- 不要提交导师私人联系方式之外的敏感信息
- 不要提交 API key
- 不自动发送套磁邮件
- 生成材料必须由用户最终确认
- 项目不承诺录取概率或录取结果

### CONTRIBUTING.md

需要说明：

- 如何安装依赖
- 如何启动后端
- 如何启动前端
- 如何运行测试
- 如何提交 issue
- 如何提交 PR
- 如何新增适配器
- 如何处理隐私数据

### Git 提交与推送规范

本项目要求每个可识别的开发步骤都留下对应的 Git commit，保证需求、代码、测试和文档可以被追踪。这里的“每一步”指一个可独立说明和验证的逻辑任务，不要求每修改一个文件就单独提交。

#### 基本原则

- 开始开发前确认当前分支和工作区状态，避免覆盖他人修改
- 一个 commit 只解决一个逻辑问题，避免把无关格式化、重命名和功能混在一起
- 功能代码、测试、必要文档应尽量在同一个逻辑 commit 中保持一致
- 每个 commit 都必须能够说明改了什么、为什么改、如何验证
- 提交前不得包含真实学生资料、真实导师私密信息、API key、`.env` 或生成产物
- 不使用 `git add .` 盲目提交，优先按文件或功能范围显式暂存
- 不改写已经推送且被他人依赖的公共历史；修复已发布内容时使用新的修复 commit

#### Commit 格式

采用 Conventional Commits 风格，提交标题使用英文类型和中文说明：

```text
<type>(<scope>): <简洁说明>
```

常用类型：

- `feat`：新增用户可见功能
- `fix`：修复错误或行为回归
- `docs`：只修改文档
- `test`：新增或调整测试
- `refactor`：不改变外部行为的代码重构
- `build`：依赖、构建或打包配置
- `ci`：持续集成配置
- `chore`：其他维护性变更
- `security`：安全、隐私或敏感信息防护

示例：

```text
feat(advisor): 增加导师主页 URL 抓取与手动粘贴兜底
test(advisor): 覆盖来源抓取失败时的手动输入分支
docs(workflow): 补充导师信息采集字段和证据要求
feat(presentation): 支持生成可编辑紫罗兰主题 PPTX
fix(material): 阻止缺少证据来源的导师结论进入报告
```

标题要求：

- 使用动词，说明结果而不是过程
- 控制在 72 个字符以内
- 不使用“修改一些代码”“更新版本”等无法审计的描述
- 不在 commit 标题中写入 API key、学生姓名、导师私人信息或本地绝对路径

#### Commit 正文

涉及业务逻辑、隐私、安全、数据结构或外部适配器时，必须补充正文：

```text
feat(advisor): 增加导师来源手动粘贴兜底

背景：
- URL 抓取可能受 robots、登录限制或网页结构变化影响。

变更：
- 增加手动粘贴入口。
- 保留原始文本和来源类型。
- 将抓取失败原因写入来源记录。

验证：
- pytest -q
- 手动验证抓取失败后仍可创建导师来源。

边界：
- 不自动判断来源真实性。
- 不自动发送联系邮件。
```

正文至少应包含以下信息中的适用项：

- 背景或问题
- 主要变更
- 影响范围
- 测试和验证命令
- 隐私、证据链或兼容性边界
- 关联 issue、阶段或任务编号

#### 每个开发步骤的提交流程

完成一个阶段性任务后，按以下顺序执行：

```bash
git status --short
git diff --check
git diff

# 运行与本次修改相关的检查
pytest -q

# 只暂存本次任务涉及的文件
git add docs/10_open_source_readiness.md CONTRIBUTING.md

git diff --cached --check
git diff --cached
git commit -m "docs(repo): 补充 Git 提交与推送规范"
git status --short
```

如果任务涉及前端或其他语言，应增加对应检查，例如：

```bash
node --check app/frontend/app.js
python -m compileall -q app integrations tests
```

提交完成后，应确认工作区干净，再推送：

```bash
git log -1 --stat
git push origin <当前分支>
```

如果当前分支尚未设置远程跟踪分支：

```bash
git push -u origin <当前分支>
```

#### 分支与推送策略

- `main` 只保留可运行、可验证的版本
- 新功能使用短生命周期分支，例如 `feat/advisor-intake`
- 文档、测试和修复也使用可表达目的的分支名
- 合并前必须通过本地测试和 CI
- 不直接强制推送 `main`
- 不提交 merge conflict、临时调试文件或未完成的半成品
- 大功能拆成多个有顺序的 commit，每个 commit 都应尽量可理解、可回滚
- 合并请求正文应说明背景、变更、验证结果、隐私影响和已知限制

#### Commit 检查清单

每个逻辑任务完成后确认：

- [ ] commit 只包含当前逻辑任务
- [ ] commit 标题符合 Conventional Commits
- [ ] 正文记录背景、变更和验证
- [ ] 测试或静态检查已执行
- [ ] 没有真实学生资料、真实私人联系方式或密钥
- [ ] 没有复制外部项目源码或原始注释
- [ ] 文档、CHANGELOG 或迁移说明已同步（如适用）
- [ ] `git diff --cached --check` 无错误
- [ ] commit 后工作区状态符合预期
- [ ] 推送前已确认目标远程仓库和分支

### CHANGELOG.md

采用简单格式：

```text
## Unreleased

### Added
- ...

### Changed
- ...

### Fixed
- ...
```

## 示例数据

需要提供匿名示例，而不是真实用户材料。

建议目录：

```text
workspace.example/
├── profiles/
│   └── sample_student_profile.json
├── advisor_sources/
│   └── sample_advisor_homepage.txt
├── targets/
│   └── sample_target.json
├── applications/
│   └── sample_application.json
├── generated/
│   ├── sample_match_report.md
│   ├── sample_contact_email.md
│   ├── sample_interview_questions.md
│   └── sample_ppt_outline.md
└── reports/
    └── sample_dashboard.html
```

示例数据原则：

- 学生姓名匿名
- 学校可虚构
- 导师可使用虚构姓名和模拟主页文本
- 不使用真实成绩单、真实身份证明、真实联系方式
- 如果使用真实公开导师页面作为示例，必须只保留短摘要和来源链接，不复制大段正文

## CI 规划

第一版 CI 可以简单但必须有。

建议检查：

- Python 单元测试
- 后端 import 检查
- 前端 build 检查
- schema 测试
- `.env` 泄露检查
- `workspace/` 是否被误提交
- API key 模式扫描
- Markdown 链接或格式基础检查

建议文件：

```text
.github/workflows/ci.yml
```

第一版可执行：

```bash
pytest
npm run build
```

如果前端尚未搭建，CI 可以先只检查 Python 和文档。

## 测试规划

建议测试目录：

```text
tests/
├── test_advisor_source_schema.py
├── test_target_schema.py
├── test_match_report_schema.py
├── test_workspace_gitignore.py
├── test_no_secret_committed.py
└── test_presentation_engine_adapter_contract.py
```

优先测试：

- 导师 URL 抓取失败时是否允许手动粘贴兜底
- 生成内容是否保留 evidence 引用
- `workspace/` 是否不会进入 Git
- API key 是否不会出现在仓库文件中
- `presentation_engine` 适配器是否能在未配置时优雅降级

## 外部项目边界

本项目会借鉴或集成外部参考项目。文档中可以明确写出参考项目路径、参考模块和借鉴点，但最终代码中使用中性命名：

- `/home/bubble/agent/ai-job-search-master`
- `/home/bubble/agent/居丽叶简历项目2：PPTAgent`

开源边界：

- 不复制两个项目的整目录
- 不把它们作为本项目源码的一部分提交
- `integrations/` 只保留自有适配器
- 代码包名使用 `workflow_engine`、`presentation_engine` 等中性命名
- 如果复用单个底层函数，必须确认许可证允许，并在文件头或 NOTICE 中标注来源
- README 可以写 inspired by / integrates with，但不能误导为 fork 或官方衍生项目
- PPTAgent 中的 ViT / vision 模型能力不进入本项目默认依赖；未来如需参考 PPT 页面理解、版式归纳或视觉评分，应通过可选外部运行时、独立 extras 或 adapter 调用
- 主项目默认依赖不加入 `torch`、ViT 模型权重或本地视觉推理栈，避免把 MVP 变成重模型项目

## 代码注释规范

开源项目中的注释需要保持克制、准确、可维护。

要求：

- 注释说明设计意图、约束、风险和兼容性
- 不用注释复述显而易见的代码
- 不在普通业务代码中写参考项目原名
- 适配器代码可以说明“external presentation engine”或“external workflow reference”，但避免直接暴露原项目名
- 如果复用单个外部函数，按许可证要求在文件头、`NOTICE` 或第三方声明中标注来源
- 不保留外部项目的大段原注释
- 临时调研说明写入 `docs/`，不要写进代码注释
- 安全、隐私、证据链相关逻辑必须有简短注释说明原因

推荐注释：

```python
# Preserve the original source text so every generated claim can be audited later.
```

不推荐注释：

```python
# Copied from <external project>.
# Set x to y.
```

## 路线图

建议创建：

```text
docs/ROADMAP.md
```

初步路线：

### MVP

- 中文保研硕博申请
- 真实导师 URL 抓取 + 手动粘贴兜底
- 学生画像
- 导师匹配分析
- 套磁邮件
- 面试问题
- PPT 大纲或 `presentation_engine` 适配

### V1

- 完整 Web UI
- 演示文稿生成能力直接调用
- 申请状态看板
- HTML 报告
- 匿名 Demo 数据
- 基础 CI

### V2

- 导师论文方向分析
- 批量目标管理
- 多目标对比
- 材料质量检查
- 强化学习结构生成优化

### V3

- 多用户
- 机构版
- 部署版
- 更完整的隐私与权限控制

## 开源发布前检查清单

- [ ] README 能让新用户 5 分钟内理解项目
- [ ] `.env.example` 存在且不包含真实 key
- [ ] `.gitignore` 忽略 `workspace/`
- [ ] 示例数据全部匿名
- [ ] 没有复制外部参考项目整目录
- [x] `integrations/` 只有自有适配器
- [x] 代码注释符合规范，没有大段外部项目注释或无意义注释
- [x] LICENSE 已选择（MIT）
- [ ] SECURITY.md 已说明隐私和 API key 风险
- [x] CI 至少能跑基础测试
- [ ] 文档说明项目不承诺录取结果
