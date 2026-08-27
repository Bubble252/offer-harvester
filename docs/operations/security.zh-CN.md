# 安全与隐私

[English](security.md)

Offer Harvester 面向可能包含敏感学生申请资料的场景。公开仓库只包含代码、合成示例
和说明文档。

## 绝不能提交

- `.env`、provider key、插件 token、数据库连接串、私钥或 cookies
- 真实简历、成绩单、证书、推荐信或联系记录
- 原始邮箱导出或完整私密邮件正文
- 真实学生的生成材料
- 私有 workspace、模型 checkpoint 或外部项目源码目录

真实本地资料放在 `workspace/`；合成示例使用 `workspace.example/` 或 `workspace.demo/`。
提交 PR 前运行 `make security`。

## 证据与用户控制

- `unconfirmed` 字段可以进入草稿，但质量报告必须明确标出。
- `rejected` 字段不能作为生成材料的证据。
- 网页补充的学生资料在用户确认前只能是 candidate。
- 公开导师和社区内容默认是来源信号，不是官方事实。
- 生成材料、邮件信号、memory promotion、tracker 更新和外部同步都必须经过对应的
  用户确认路径。

## No-Send 边界

应用和 P0 Skill 不会自动发送套磁信、提交申请、上传附件，也不会冒充推荐人。DSH 工具
同样只返回 candidate，并通过 Offer Harvester 控制面访问数据，不直接读取 workspace。

## 外部 Provider

启用 LLM、embedding、reranker、OCR、云数据库或外部 Agent provider 前，应检查隐私路由
和 provider 的数据处理条款。除非用户明确授权并经过审查，学生私有证据保持本地处理。
DSH 使用独立插件 token，不复用 LLM 或数据库凭据。

## 报告问题

不要在公开 issue 中发布敏感内容。分享复现信息前删除姓名、邮箱、URL、来源正文、
token、截图和 workspace 路径；有配置的情况下通过维护者私密安全渠道报告。
