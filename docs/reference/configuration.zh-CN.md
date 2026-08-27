# 配置参考

[English](configuration.md)

本地配置时复制 `.env.example` 为 `.env`。`.env` 已被忽略，绝不能提交。空值会有意
选择本地 fallback。

## 基础运行时

| 变量 | 默认值 | 含义 |
| --- | --- | --- |
| `APP_ENV` | `development` | 运行环境标签 |
| `BACKEND_HOST` | `127.0.0.1` | 绑定地址；私有资料默认保持回环 |
| `BACKEND_PORT` | `8000` | 本地 HTTP 端口 |
| `WORKSPACE_DIR` | `./workspace` | 本地事实源目录 |
| `PRESENTATION_ENGINE_ROOT` | 空 | 可选外部演示适配器根目录 |

## LLM 与检索

| 变量 | 默认值 | 含义 |
| --- | --- | --- |
| `LLM_PROVIDER` | `openai_compatible` | LLM 适配器选择 |
| `OPENAI_BASE_URL` | 示例 provider | OpenAI-compatible 基础 URL |
| `OPENAI_MODEL` | 示例 provider | 模型名称 |
| `OPENAI_WIRE_API` | `responses` | `responses` 或 `chat` wire 模式 |
| `RAG_STORAGE_BACKEND` | `json` | 本地存储适配器 |
| `RAG_EMBEDDING_PROVIDER` | `hash` | hash、配置的 API 或本地适配器 |
| `RAG_RERANKER` | `noop` | noop、词法、API 或本地适配器 |

Provider key 都是运行时 secret。启用 provider 前，应确认该适配器允许发送哪些数据。
学生私有证据必须遵循隐私路由。

## 本地模型配置位

`LOCAL_LLM_*`、`LOCAL_EMBEDDING_*` 和 `LOCAL_RERANK_*` 为本地服务预留配置位，但不会
自动安装或启动模型服务。PyTorch、Transformers、PaddleOCR、ViT 和 vLLM 都是可选重型
依赖。

## SiliconFlow 配置位

`SILICONFLOW_*` 配置现有 OpenAI 形状的 embedding/rerank 适配器。除非明确启用这些
适配器，否则保持 `SILICONFLOW_API_KEY` 为空。不要把真实 key 放入示例、测试、截图或 issue。

## Public Knowledge 与云端

| 变量 | 默认值 | 含义 |
| --- | --- | --- |
| `SUPABASE_URL` | 空 | 可选 Supabase 项目 URL |
| `PUBLIC_KB_DATABASE_URL` | 空 | 可选 Postgres/pgvector 连接串 |
| `PUBLIC_KB_SYNC_MODE` | `dry-run` | 同步模式，审查前保持 dry-run |

本地运行不需要云端同步。云端数据库不能绕过本地证据和隐私治理成为新的事实源。

## DSH 插件

| 变量 | 默认值 | 含义 |
| --- | --- | --- |
| `OFFER_HARVESTER_PLUGIN_AUTH_MODE` | `local` | `local`、`token` 或显式 disabled |
| `OFFER_HARVESTER_PLUGIN_TOKEN` | 空 | 独立插件 token，不是 LLM key |
| `OFFER_HARVESTER_PLUGIN_SCOPES` | `skill:run,...` | 允许的逗号分隔 scope |
| `OFFER_HARVESTER_PLUGIN_ALLOW_REMOTE_PRIVATE` | `false` | 是否显式允许远程私有资料 |

回环开发使用 `local`，远程插件使用 `token`。除非已经审查隐私路由和部署，否则保持
`OFFER_HARVESTER_PLUGIN_ALLOW_REMOTE_PRIVATE=false`。

## 只读邮件连接器

| 变量 | 默认值 | 含义 |
| --- | --- | --- |
| `EMAIL_CREDENTIAL_SERVICE` | `offer-harvester.email` | Gmail/QQ 凭据使用的系统 keyring service 名称 |
| `GMAIL_OAUTH_CLIENT_ID` | 空 | 本地 Gmail OAuth client ID |
| `GMAIL_OAUTH_CLIENT_SECRET` | 空 | 本地 Gmail OAuth client secret（该 client 需要时） |
| `GMAIL_OAUTH_REDIRECT_URI` | 本地 callback | Gmail 只读授权使用的本地回调地址 |

Gmail token 和 QQ 授权码只保存在系统 keyring，不进入 workspace 或 Git。详见
[只读邮件连接器](../guides/email-connectors.zh-CN.md)。

## 代理与下载

`HTTP_PROXY` 和 `HTTPS_PROXY` 可以指向经过允许的本地代理或软件包镜像。凭据必须通过
宿主环境或 secret manager 提供，不要写入 `.env.example`。
