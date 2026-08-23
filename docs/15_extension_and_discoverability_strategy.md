# 轻量外延与项目发现性策略

## 目标

这份文档回答两个问题：

1. 主项目之外，是否有必要做一些可以向外延伸的轻量化工具。
2. 如果希望项目更容易被 GitHub 用户发现，哪些做法是真正有效的。

结论先写在前面：**有必要做，但只能围绕核心能力拆分，不要先做成多个彼此割裂的小项目。**

优先级建议是：

1. 可迁移的 `skill`。
2. 轻量、窄功能的 `app` 或子页面。
3. 仅当存在稳定的 JavaScript/TypeScript 公共能力时，再考虑 `npm` 包。

## 为什么要做轻量外延

当前仓库的核心价值是“保研 / 硕博申请工作台”，但真正容易传播出去的，通常不是完整工作台本身，而是其中几个清晰、可复用、可单独理解的能力。

比如：

- 导师画像抽取
- 套磁邮件审查
- 事实证据检查
- 截止日期检查
- PPT 质量检查

这些能力如果全部只藏在主应用里，会有两个问题：

- 新用户很难第一眼知道项目到底能复用什么。
- 外部用户即使不需要整个工作台，也不会愿意为了一个小任务装完整系统。

所以更合理的做法是把核心能力拆成“可嵌入、可分享、可单独演示”的外延形态。

## 适合拆出的形态

### 1. Portable skill

这是最适合当前项目的外延形式。

建议把以下能力做成可迁移 skill：

- `advisor-profiler`
- `material-drafter`
- `material-reviewer`
- `evidence-auditor`
- `deadline-checker`
- `match-rubric`

适合 skill 的原因：

- 主要是流程、规则和提示词，不依赖重前端。
- 容易复用到别的申请场景。
- 和当前仓库的 `portable skill` 方向一致。
- 可以作为项目的“可分享知识单元”，比单纯代码更容易传播。

边界：

- 不放真实学生资料。
- 不放私密导师联系方式。
- 不把 workflow 变成不可审计的黑盒。

### 2. 轻量 app

这里的 app 不是再复制一套完整工作台，而是一些窄而实用的独立入口。

更适合做成 app 的方向：

- 导师主页快速体检页
- 套磁邮件证据检查页
- 面试 PPT 大纲检查页
- 申请目标小看板

这类 app 的价值在于：

- 可以单独展示。
- 可以截成演示素材。
- 适合引流到主项目。

边界：

- 只做一个明确任务。
- 默认本地优先，避免把隐私交给外部服务。
- 不把复杂设置塞进第一页。

### 3. `npm` 包

这个方向**不是当前第一优先级**，但值得保留。

只有在下面情况同时成立时，才值得做：

- 项目里出现稳定的 JavaScript / TypeScript 公共逻辑。
- 该逻辑确实会被前端、插件或其他项目复用。
- 包的边界足够清晰，能独立维护版本。

更可能适合做成 `npm` 包的内容：

- schema 校验工具
- 轻量 UI helpers
- 导入导出工具
- 面向浏览器的文档解析辅助组件

不建议现在就做 `npm` 包的原因：

- 当前主栈还是 Python / FastAPI。
- 过早拆包只会增加发布和维护成本。
- 如果没有真实 JS 复用场景，`npm` 包只会变成形式主义。

## star 增长的“规则”

严格说，没有一个官方的“刷 star 公式”。更接近事实的说法是：**star 是项目可发现性、可理解性、可尝试性和可复用性共同作用的结果。**

从 GitHub 官方文档能直接确认的几件事是：

- README 是访客最先看到的内容之一，用来说明项目有用、能做什么、怎么开始。
- topics 会帮助别人按主题找到项目，且会出现在仓库主页上。
- social preview 能改善别人转发仓库链接时的展示效果。
- release notes 能让版本变化更清楚，降低“这个项目还活不活”的疑虑。

所以，如果目标是稳步增加 star，更有效的不是追求夸张标题，而是把下面几件事做到位：

1. 一眼看懂。
2. 一分钟跑起来。
3. 一次就能看到 demo。
4. 每个核心能力都有可复用的最小单元。
5. 发布节奏稳定，变化可追踪。

## 可执行的发现性动作

建议优先做这些：

- README 首屏写清项目是什么、适合谁、现在能做什么。
- 选少量精准 topics，不要堆无关标签。
- 补一个清晰的 social preview 图。
- 保持 `CHANGELOG` 和 release notes 可读。
- 把 demo 截图和 walkthrough 放在容易点到的位置。
- 把可复用能力拆成 skill 或轻量工具，而不是只藏在主应用里。

不建议做这些：

- 虚假的下载量 badge。
- 没有实际发布的 npm / PyPI badge。
- 和项目无关的热门 topic。
- 夸大不稳定能力，或者把 future work 写成现状。

## 推荐推进顺序

### 第一层：主项目稳定

- 保持本地优先工作台不变。
- 继续固化 `README`、`CHANGELOG`、`SECURITY`、`CONTRIBUTING`。
- 确保 demo 和截图稳定。

### 第二层：portable skill

- 先把最成熟的 3 到 5 个 workflow 抽成 skill。
- 每个 skill 都有清晰输入、输出、边界和示例。
- 这些 skill 既能服务主项目，也能单独传播。

### 第三层：轻量 app

- 先做一个最能独立展示的窄功能页面。
- 页面只解决一个任务。
- 页面可以直接链接回主项目。

### 第四层：`npm` 包

- 只在确实需要 JS 复用时再拆。
- 先从 schema / helper 层开始。
- 不要为了“看起来像生态”而拆包。

## 执行检查清单

- [ ] 确认哪些能力适合做 skill。
- [ ] 确认是否存在一个值得单独展示的轻量 app。
- [ ] 确认当前是否真的有 JS/TS 公共逻辑值得抽成 `npm` 包。
- [ ] 选择 5 个以内的 GitHub topics。
- [ ] 准备 social preview 图。
- [ ] 在 README 中补上 demo、release 和可复用能力入口。
- [ ] 保持 changelog 和 release notes 的节奏。

## Git 提交与推送建议

这个阶段建议按逻辑拆 commit，而不是把文档、README 和计划混在一个大提交里。

### 1. 文档提交

```bash
git status --short
git diff --check
git add docs/15_extension_and_discoverability_strategy.md docs/03_execution_plan.md README.md README.zh-CN.md
git commit -m "docs(strategy): 补充轻量外延与发现性规划"
git push origin <当前分支>
```

### 2. 后续实现提交

如果后面真的开始拆 skill 或轻量 app，再单独提交：

```bash
git status --short
git diff --check
git add <本次任务涉及文件>
git commit -m "feat(skill): 提炼可复用导师画像流程"
git push origin <当前分支>
```

## 参考来源

- GitHub README 文档: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes
- GitHub topics 文档: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics
- GitHub social preview 文档: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview
- GitHub release notes 文档: https://docs.github.com/en/repositories/releasing-projects-on-github/automatically-generated-release-notes
