# Grad Apply Workflow

<p align="center">
  <img src="app/frontend/assets/logo.png" alt="Grad Apply Workflow logo" width="220" />
</p>

面向保研硕博申请的本地 Web 工作台，帮助学生基于真实导师信息完成稳妥型导师匹配、中文申请材料生成、面试准备和申请状态追踪。

## MVP 功能

- 学生资料上传与画像抽取
- 导师 URL 抓取与手动粘贴兜底
- 导师/实验室/项目目标管理
- 稳妥型匹配分析
- 中文套磁邮件生成
- 中文面试问题生成
- 5 页面试展示 PPT 大纲生成
- 申请状态追踪

## Demo 截图

完整带图说明见 [Demo Walkthrough](docs/11_demo_walkthrough.md)。

- [申请概览](docs/assets/demo/01-dashboard.png)
- [学生画像与字段证据](docs/assets/demo/02-profile-evidence.png)
- [导师来源与画像](docs/assets/demo/03-advisor-sources.png)
- [匹配报告](docs/assets/demo/05-match-report.png)
- [材料质量审查](docs/assets/demo/06-material-quality.png)
- [可编辑 PPTX 下载](docs/assets/demo/07-pptx-download.png)
- [申请进度报告](docs/assets/demo/08-progress-report.png)

## 快速开始

```bash
cd app/backend
python -m pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

然后打开：

```text
http://127.0.0.1:8000
```

## 隐私说明

真实学生资料、导师联系记录和生成材料默认写入 `workspace/`，该目录不会进入 Git。不要提交 `.env`、真实 API key、真实成绩单或真实套磁邮件。

## 外部参考边界

本项目文档会明确记录参考了哪些外部项目和模块；最终代码使用自有实现和中性命名，不包含外部项目复制体。
具体参考来源和未来第三方复用要求见 `NOTICE`。当前演示文稿能力默认生成可审阅的
Markdown 大纲；配置外部引擎前不会假设存在可用的 PPTX 运行环境。
