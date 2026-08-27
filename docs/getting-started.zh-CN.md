# 快速开始

[English](getting-started.md)

## 环境要求

- Python 3.11 或更高版本
- Git
- GNU Make
- 浏览器

默认路径是本地优先。外部 LLM、Embedding、Reranker、OAuth、数据库和重型模型服务
都是可选项，运行匿名 demo 不需要它们。

## 安装

```bash
git clone https://github.com/Bubble252/offer-harvester.git
cd offer-harvester
python -m venv .venv
. .venv/bin/activate
make install
```

如果依赖下载较慢，可以在执行 `make install` 前配置经过允许的国内镜像或本地 HTTP
代理。不要把代理凭据写入 Git。

## 启动空白工作区

```bash
make run
```

打开 `http://127.0.0.1:8000`。同一服务还提供交互式 API 文档
`http://127.0.0.1:8000/docs`，以及机器可读的契约
`http://127.0.0.1:8000/openapi.json`。

应用默认把本地数据保存到 `workspace/`，该目录被 Git 忽略。只有需要配置 provider
时才复制 `.env.example` 为 `.env`。

## 启动匿名 Demo

```bash
make run-demo
```

命令会用匿名合成数据重建 `workspace.demo/` 并启动应用。Demo 包含学生画像、公开
导师来源摘要、申请目标、匹配报告、候选材料、PPTX 和进度报告，不包含真实学生资料。

只重建 Demo 数据：

```bash
make seed-demo
```

安装 Playwright 后更新截图：

```bash
python tools/capture_demo_screenshots.py \
  --base-url http://127.0.0.1:8000 \
  --output-dir docs/assets/demo
```

## 第一次使用

1. 打开“学生资料”，粘贴或上传本地原始资料。
2. 检查字段级证据，把每个字段标为 `confirmed`、`unconfirmed`、`rejected` 或
   `needs_review`。
3. 打开“导师资料”，添加公开 URL，或在抓取失败时粘贴文本。
4. 创建申请目标。
5. 生成匹配报告和候选材料。
6. 检查证据引用、质量发现和风险标签。
7. 自行核对事实后，再复制或下载结果。

产品不会把草稿当作最终提交。所有生成内容都是候选材料，仍受用户确认和 no-send
边界保护。

## 常见问题

### 端口被占用

```bash
make run PORT=8001
```

然后打开 `http://127.0.0.1:8001`。

### 浏览器打不开 127.0.0.1

确认服务和浏览器运行在同一个主机或网络命名空间。容器、远程终端或隔离沙盒内启动
的进程可能无法被宿主浏览器访问。只有在可信本地环境中才应调整绑定地址，默认不要
把私有工作区暴露到公网。

### 外部 provider 失败

本地 hash embedding、词法 reranker、确定性抽取和 PPT fallback 都是有意保留的路径。
可以检查 `/api/llm/status`、`.env` 中的 provider 配置、网络和隐私路由。不要在 issue
中粘贴 API key。

### Demo 数据过期

停止服务，执行 `make seed-demo`，再重新启动。Demo workspace 可以删除，不应存放真实
申请资料。

## 验证当前 checkout

```bash
make verify
```

该命令会运行 Python lint/格式检查、测试、文档和公开边界检查、OpenAPI 契约校验、前端
语法检查、编译检查，以及 DSH 适配器契约测试。
