# Evidence Claim Audit Contract / 证据声明审计契约

Input is a JSON object with a non-empty `claims` array. Each claim requires `text`; it may include `claim_type`, `source_refs`, `status`, and `time_sensitive`.

Allowed statuses are `supported`, `unsupported`, `stale`, and `needs_confirmation`.

输出必须保留每条声明的文本、来源引用、状态和阻塞原因。缺来源、冲突、过期或未确认不能被自动改为通过。

The Skill produces findings only. The Offer Harvester control plane decides whether a candidate can become a confirmed fact, final material, or tracker update.
