# Demo Walkthrough

这份说明用于快速展示 Grad Apply Workflow 的核心闭环：从学生资料、导师来源、申请目标，到匹配分析、材料审查、PPTX 生成和进度报告。

演示数据来自 `workspace.demo/` 的匿名样例。学生信息为虚构匿名资料；导师来源使用公开网页摘要和来源链接。真实学生资料、API key、真实套磁邮件和个人隐私数据不应进入 Git。

## 演示主线

```text
学生资料落盘
-> 字段级证据与确认
-> 导师公开来源采集
-> 创建申请目标
-> 生成匹配分析
-> 生成套磁邮件并通过 reviewer / auditor
-> 生成可编辑 PPTX
-> 输出申请进度报告
```

## 1. 申请概览

![申请概览](assets/demo/01-dashboard.png)

首页展示当前申请目标、已联系导师、待推进目标和已生成材料。它不是营销页，而是进入实际申请工作流的操作台。

这个页面用于回答两个问题：

- 现在有哪些申请目标需要推进
- 最近生成过哪些材料，是否需要继续复核

## 2. 学生画像与字段证据

![学生画像与字段证据](assets/demo/02-profile-evidence.png)

学生资料可以来自本地上传或手动粘贴。原始资料会先保存到 `workspace/user_documents/`，再抽取成结构化 `StudentProfile`。

字段级确认状态包括：

- `unconfirmed`：可用于草稿，但必须在质量报告中提示
- `confirmed`：用户已确认，可作为可靠事实
- `rejected`：用户否认，生成材料时禁止主动使用
- `needs_review`：证据不足或存在冲突，需要复核

这一步的重点是避免把未确认事实直接写成正式申请材料。

## 3. 导师来源与画像

![导师来源与画像](assets/demo/03-advisor-sources.png)

导师资料优先来自学校、学院、实验室或招生通知等公开来源。URL 抓取失败时，用户可以手动粘贴正文作为兜底。

导师画像会记录：

- 来源类型和抓取状态
- 导师姓名、学校、学院、职称、实验室
- 研究方向、招生要求、代表论文和风险提示
- 来源证据数量和身份确认状态

系统的约束是：导师方向、招生要求和匹配结论必须能追溯到来源。

## 4. 申请目标追踪

![申请目标追踪](assets/demo/04-target-tracker.png)

从导师画像可以创建申请目标，并记录申请类型、申请轮次、截止日期、当前状态和下一步行动。

目标池承担后续材料生成的上下文入口。匹配分析、套磁邮件、面试问题和 PPT 都围绕某个具体目标生成。

## 5. 匹配分析报告

![匹配分析报告](assets/demo/05-match-report.png)

匹配分析不是录取概率预测，而是稳妥型申请判断。报告会输出：

- 匹配等级和分数
- 学生经历与导师方向的匹配点
- 风险与缺口
- 下一步建议

后续材料生成会引用匹配报告，避免套磁邮件只写泛泛的“我对您的方向很感兴趣”。

## 6. 材料质量审查

![材料质量审查](assets/demo/06-material-quality.png)

套磁邮件生成走 `MaterialDraftAgent -> MaterialReviewAgent -> EvidenceAuditAgent` 主链路。

质量区域展示三层结果：

- 基础质量检查：材料是否关联证据、是否过度承诺、是否模板化
- Reviewer：检查空泛、夸大、导师方向不贴合和面试不可解释
- Evidence Auditor：逐项检查材料声明是否来自学生画像、导师来源或匹配报告

这一步是本项目从普通材料生成器变成可审计 Agent 工作流的关键。

## 7. 可编辑 PPTX 下载

![可编辑 PPTX 下载](assets/demo/07-pptx-download.png)

当前 MVP 使用本地 `LocalPptxAdapter` 生成可编辑 PPTX，适合面试展示场景。PPTAgent 深度集成仍放在阶段 11，后续通过可选适配器接入参考模板学习、版式选择和评估能力。

当前边界：

- 可以生成并下载可编辑 PPTX
- 不复制 PPTAgent 外部项目源码
- 参考 PPT 模板上传和外部引擎运行时暂未作为 MVP 必需能力

## 8. 申请进度报告

![申请进度报告](assets/demo/08-progress-report.png)

进度报告汇总本地 workspace 中的画像、导师、目标、材料和状态记录，用于复盘当前申请准备情况。

报告不包含录取概率预测，也不替代用户人工判断。它的作用是帮助用户知道哪些材料已生成、哪些事实仍需确认、哪些目标还要推进。

## 复现截图

先启动 demo 服务：

```bash
cd app/backend
WORKSPACE_DIR=/home/bubble/agent/grad-apply-workflow/workspace.demo ../../.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8001
```

然后在项目根目录运行截图脚本：

```bash
python3 tools/capture_demo_screenshots.py --base-url http://127.0.0.1:8001 --output-dir docs/assets/demo
```

截图脚本依赖本地 Playwright。它只用于展示素材更新，不是后端运行时依赖。
