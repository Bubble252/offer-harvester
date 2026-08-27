# Source Connector Manifest / 来源连接器清单

Required JSON fields:

- `connector_id`, `name`, `version`
- `url_patterns`, `field_mapping`, `access_method`
- `robots_checked_at`, `tos_checked_at`
- `rate_limit_per_minute`, `refresh_interval_days`, `fallback`

`access_method` must be one of `public_http`, `official_api`, `authorized_export`, or `authorized_oauth`.

禁止以 `bypass_login`、`captcha_bypass` 或 `private_group` 作为访问方式。社区内容只能进入 `risk_signal`，不能直接成为 confirmed fact。
