---
name: source-connector-authoring
description: Design and validate safe source connector manifests for public graduate-admission, policy, advisor, lab, and community sources. Use when adding a crawler, refresh job, source connector, source access policy, field mapping, live test, or safe fallback.
---

# Source Connector Authoring

1. Read `references/manifest-schema.md` before creating or editing a connector.
2. Define a source-specific allowlist, field mapping, refresh interval, rate limit, and fallback.
3. Record robots/ToS review date and allowed access method.
4. Use public pages, official APIs, or explicitly authorized exports only.
5. Validate the manifest with `scripts/validate_manifest.py --input <manifest.json>`.

## Hard Boundaries

- Do not bypass login walls, CAPTCHA, private-group access, robots controls, or rate limits.
- Do not treat a community post as confirmed fact; emit it only as a reviewable risk signal.
- Do not store full community content unless its source policy allows it and a deletion path exists.
- Do not register a connector until its live test and human policy review pass.

## 中文说明

1. 创建或编辑 connector 前先阅读 `references/manifest-schema.md`。
2. 定义来源专属 allowlist、字段映射、刷新间隔、限速与失败 fallback。
3. 记录 robots/ToS 审查日期和允许的访问方式。
4. 只使用公开页面、官方 API 或明确授权的导出。
5. 使用 `scripts/validate_manifest.py --input <manifest.json>` 校验 manifest。

### 强制边界

- 不绕过登录墙、CAPTCHA、私密群组权限、robots 控制或限速。
- 社区帖子不是确认事实，只能输出为待复核风险信号。
- 除非来源策略允许且有删除路径，否则不保存完整社区正文。
- connector 通过 live test 和人工策略审查前不得注册。
