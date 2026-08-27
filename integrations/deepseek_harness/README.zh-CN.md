# Offer Harvester DeepSeek Harness 集成

[English](README.md)

本目录是 DeepSeek Harness（DSH）的本地孵化适配层。它把受控的 Offer Harvester 候选结果暴露为 DSH 工具，但不让 DSH 成为事实源或状态控制器。

## 提供的工具

- `offer_harvester_draft_contact_email`
- `offer_harvester_advisor_due_diligence`
- `offer_harvester_recommendation_letter_helper`
- `offer_harvester_audit_material`

所有工具均为候选结果并带 `no_send`。Offer Harvester FastAPI 控制面仍负责用户画像、证据审计、用户确认和 workspace 落盘。

## 安全约束

- 不发送、不提交邮件、推荐信、表单或申请。
- 适配层不能直接写入 profile、政策事实或 tracker 状态。
- 社区或口碑文本只能是待复核风险信号，不能作为确认事实。
- 材料审计只生成追踪和报告，不改写被审计材料。
- DSH 请求只申请最小权限：`skill:run`、`advisor:report` 或 `material:audit`。

## 本地接入

1. 启动 Offer Harvester：`http://127.0.0.1:8000`。
2. 把 `cordis.yml.example` 复制到 DSH 的组合配置中，并调整 `apiBaseUrl`。
3. 本地 loopback 开发保持 `OFFER_HARVESTER_PLUGIN_AUTH_MODE=local`。
4. 只要改为远程部署，就设为 `OFFER_HARVESTER_PLUGIN_AUTH_MODE=token`，生成足够长的 `OFFER_HARVESTER_PLUGIN_TOKEN`，并在 DSH 插件中配置同一 token。
5. 除非服务端显式允许远程私有数据，否则保持 `privacyMode: metadata_only`。

`workspaceLabel` 有意不实现为文件路径。workspace 的选择权始终在服务端，避免 DSH 工具选择任意本地目录。

能够根据 JSON Schema 渲染设置的宿主可使用
[`settings.schema.json`](settings.schema.json)。它声明 URL、token、privacy mode、
超时、启用工具列表和仅展示用 workspace label。`pluginToken` 标记为 write-only，
不能被导出到示例配置中。

## 验证

```bash
cd integrations/deepseek_harness
npm test
```

这里的测试是不联网的 HTTP 合约测试。仓库本身不强制安装 DSH runtime；需要挂载 `src/plugin.ts` 时，再按 DSH 官方的 Cordis loader 说明安装和运行。

## 边界

这不是独立发布的 DSH distribution，也不复制 DSH runtime。它是一个稳定前的适配边界；接口稳定后再考虑发布 package 或拆出独立仓库。
