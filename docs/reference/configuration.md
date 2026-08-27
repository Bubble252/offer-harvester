# Configuration Reference

[简体中文](configuration.zh-CN.md)

Copy `.env.example` to `.env` for local configuration. `.env` is ignored and must never
be committed. Empty values deliberately select local fallbacks.

## Core Runtime

| Variable | Default | Meaning |
| --- | --- | --- |
| `APP_ENV` | `development` | Runtime environment label |
| `BACKEND_HOST` | `127.0.0.1` | Bind address; keep loopback for private data |
| `BACKEND_PORT` | `8000` | Local HTTP port |
| `WORKSPACE_DIR` | `./workspace` | Local source-of-truth directory |
| `PRESENTATION_ENGINE_ROOT` | empty | Optional external presentation adapter root |

## LLM And Retrieval

| Variable | Default | Meaning |
| --- | --- | --- |
| `LLM_PROVIDER` | `openai_compatible` | LLM adapter selection |
| `OPENAI_BASE_URL` | provider example | OpenAI-compatible base URL |
| `OPENAI_MODEL` | provider example | Model name |
| `OPENAI_WIRE_API` | `responses` | `responses` or `chat` wire mode |
| `RAG_STORAGE_BACKEND` | `json` | Local storage adapter |
| `RAG_EMBEDDING_PROVIDER` | `hash` | `hash`, configured API, or local adapter |
| `RAG_RERANKER` | `noop` | `noop`, lexical, API, or local adapter |

Provider keys are runtime secrets. Use a provider only after checking what data its adapter
is allowed to send. Private student evidence must follow the configured privacy route.

## Local Model Slots

`LOCAL_LLM_*`, `LOCAL_EMBEDDING_*`, and `LOCAL_RERANK_*` reserve configuration slots for
local services. They do not install or start a model server. Heavy dependencies such as
PyTorch, Transformers, PaddleOCR, ViT, and vLLM are optional.

## SiliconFlow Slots

`SILICONFLOW_*` variables configure the existing OpenAI-shaped embedding/rerank adapters.
Leave `SILICONFLOW_API_KEY` empty unless you intentionally enable those adapters. Do not
use a real key in examples, tests, screenshots, or issue reports.

## Public Knowledge And Cloud

| Variable | Default | Meaning |
| --- | --- | --- |
| `SUPABASE_URL` | empty | Optional Supabase project URL |
| `PUBLIC_KB_DATABASE_URL` | empty | Optional Postgres/pgvector connection |
| `PUBLIC_KB_SYNC_MODE` | `dry-run` | Sync mode; keep dry-run until reviewed |

Cloud sync is not required for local operation. A cloud database must not become a bypass
around the local evidence and privacy governance.

## DSH Plugin

| Variable | Default | Meaning |
| --- | --- | --- |
| `OFFER_HARVESTER_PLUGIN_AUTH_MODE` | `local` | `local`, `token`, or explicit disabled mode |
| `OFFER_HARVESTER_PLUGIN_TOKEN` | empty | Separate plugin token, never an LLM key |
| `OFFER_HARVESTER_PLUGIN_SCOPES` | `skill:run,...` | Comma-separated allowed scopes |
| `OFFER_HARVESTER_PLUGIN_ALLOW_REMOTE_PRIVATE` | `false` | Explicit remote private-data opt-in |

Use `local` for loopback development. Use `token` for remote plugin access. Keep
`OFFER_HARVESTER_PLUGIN_ALLOW_REMOTE_PRIVATE=false` unless the privacy route and deployment
are intentionally reviewed.

## Read-Only Mail Connectors

| Variable | Default | Meaning |
| --- | --- | --- |
| `EMAIL_CREDENTIAL_SERVICE` | `offer-harvester.email` | OS keyring service name for Gmail/QQ credentials |
| `GMAIL_OAUTH_CLIENT_ID` | empty | Local Gmail OAuth client ID |
| `GMAIL_OAUTH_CLIENT_SECRET` | empty | Local Gmail OAuth client secret, when required by the client |
| `GMAIL_OAUTH_REDIRECT_URI` | local callback | Local callback URL for the Gmail read-only flow |

Gmail tokens and QQ authorization codes stay in the OS keyring, not the workspace or Git.
See [Read-Only Mail Connectors](../guides/email-connectors.md).

## Proxy And Download

`HTTP_PROXY` and `HTTPS_PROXY` may point to an approved local proxy or package mirror.
Credentials must be supplied through the host environment or secret manager, not `.env.example`.
