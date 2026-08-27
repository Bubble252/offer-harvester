# 只读邮件连接器

[English](email-connectors.md)

Offer Harvester 目前提供两个可选、手动触发的邮件连接器：

- Gmail 授权码流程，只申请 `gmail.readonly` 范围。
- QQ 邮箱 IMAP，使用用户自己创建的 IMAP 授权码。

它们只用于识别信号。同步可能生成导师回复、面试、补材料、拒信、offer 或 waitlist 的
**候选项**；不会发信、删信、修改标签、下载附件，也不会在用户确认前修改 tracker。

## 凭据边界

- Gmail token 和 QQ 授权码通过 `keyring` 保存在操作系统的凭据存储中，并按本地 workspace
  隔离。
- workspace JSON 只记录非 secret 的连接元数据、同步 trace 和可审查的信号候选项。
- 原始邮箱导出、token、授权码、附件和真实邮件正文不能提交到 Git。
- 本版本只支持手动同步，不启动后台轮询、常驻调度或自动 tracker 写入。

在 Gmail 授权前，在本地 `.env` 填写：

```dotenv
EMAIL_CREDENTIAL_SERVICE=offer-harvester.email
GMAIL_OAUTH_CLIENT_ID=
GMAIL_OAUTH_CLIENT_SECRET=
GMAIL_OAUTH_REDIRECT_URI=http://127.0.0.1:8000/api/email-connectors/gmail/callback
```

## Gmail

1. 启动本地 Offer Harvester，并在 Gmail OAuth client 中配置重定向地址。
2. 调用 `POST /api/email-connectors/gmail/authorize`。
3. 在同一台本地浏览器中打开返回的授权地址并完成授权。
4. 回调只把凭据写入系统 keyring，并记录只读连接状态。
5. 调用 `POST /api/email-connectors/gmail/sync`，其中 `provider` 必须为 `gmail`。
6. 在 `/api/email-signals` 查看候选项，再明确 approve 或 reject。

```bash
curl -X POST http://127.0.0.1:8000/api/email-connectors/gmail/sync \
  -H 'Content-Type: application/json' \
  -d '{"provider":"gmail","max_messages":10,"query":"newer_than:90d"}'
```

## QQ 邮箱

1. 在 QQ 邮箱设置中开启 IMAP，并创建授权码。
2. 调用 `POST /api/email-connectors/qq/configure`，提交账号和授权码。
3. 调用 `POST /api/email-connectors/qq/sync`，其中 `provider` 为 `qq`。
4. 在更新 tracker 前逐项审查信号候选项。

```bash
curl -X POST http://127.0.0.1:8000/api/email-connectors/qq/sync \
  -H 'Content-Type: application/json' \
  -d '{"provider":"qq","max_messages":10,"mailbox_filter":"unseen"}'
```

断开连接会删除 keyring 内的凭据：

```bash
curl -X DELETE http://127.0.0.1:8000/api/email-connectors/gmail
```

## 失败处理

- 缺少 keyring 后端、缺少 Gmail 配置、OAuth state 过期或 IMAP 失败时，API 会显示错误，tracker
  保持不变。
- 按来源 hash 跳过重复的邮件候选项。
- Gmail 授权过程中若本地进程重启，需要重新开始授权；PKCE state 故意只在内存中保存十分钟。
