# 套磁邮件模板

```json
{
  "template_id": "contact_email_default_zh",
  "name": "中文套磁邮件默认模板",
  "template_type": "contact_email",
  "version": "0.1.0",
  "description": "用于生成克制、证据化、可审计的中文导师套磁邮件草稿。",
  "variables": [
    "advisor_name",
    "student_alias",
    "target_school",
    "advisor_direction",
    "student_project",
    "fit_reason",
    "request_action"
  ],
  "sample_context": {
    "advisor_name": "某导师",
    "student_alias": "匿名申请者",
    "target_school": "样例大学",
    "advisor_direction": "多模态学习",
    "student_project": "科研问答系统项目",
    "fit_reason": "项目经历和导师方向存在可解释交集",
    "request_action": "希望获得进一步交流机会"
  },
  "applicable_scenarios": [
    "初次联系导师",
    "已有目标导师来源证据",
    "学生项目和导师方向存在明确交集"
  ],
  "style_rules": [
    "避免过度承诺和录取预测",
    "每个事实应能回到 profile、advisor source 或 match report",
    "邮件正文短而具体，优先说明研究交集和下一步请求"
  ],
  "privacy_rules": [
    "模板内不得写入真实姓名、邮箱、成绩、排名或导师联系方式",
    "真实学生事实只能通过变量注入，并继续接受 evidence audit",
    "默认不包含附件正文"
  ],
  "validation_methods": [
    "manifest_required_keys",
    "variable_completeness",
    "sample_render",
    "privacy_literal_scan"
  ],
  "managed_block": "grad_apply.contact_email.default_zh"
}
```

```template
{{advisor_name}}老师您好：

我是{{student_alias}}，正在关注{{target_school}}相关推免机会。近期阅读您的公开资料后，我对您在{{advisor_direction}}方向的工作很感兴趣。

我此前参与过{{student_project}}，其中{{fit_reason}}。如果后续仍有合适的硕士或直博申请机会，我希望能进一步了解课题组的招生安排与准备重点。

{{request_action}}。感谢老师阅读。
```
