# 学院通知页 Connector

```json
{
  "connector_id": "college_notice_generic_zh",
  "name": "中文学院通知页通用映射",
  "source_type": "college_notice",
  "version": "0.1.0",
  "description": "用于描述学院推免、夏令营、预推免通知页如何映射到 AdvisorSource 或 policy knowledge source。",
  "url_patterns": [
    "https://*/notice/*",
    "https://*/news/*",
    "https://*/admission/*",
    "https://*/graduate/*"
  ],
  "field_mapping": {
    "title": "页面标题或通知标题",
    "source_url": "通知页 URL",
    "raw_text": "页面正文文本",
    "published_at": "发布日期",
    "deadline": "报名、材料提交或系统确认截止日期",
    "materials_required": "材料清单",
    "valid_for_year": "通知适用年份",
    "college": "学院或招生单位",
    "program_name": "项目或专业名称"
  },
  "access_rules": [
    "仅访问公开网页",
    "抓取前检查 robots.txt 和页面 ToS",
    "不访问登录后页面、验证码页面或付费页面",
    "失败时提示用户手动粘贴通知正文"
  ],
  "robots_policy": "如果 robots.txt 或页面说明禁止自动访问，则不执行自动抓取，只允许用户手动粘贴。",
  "tos_policy": "遵守学校、学院网站的使用条款；不高频请求，不复制大段网页正文到公开仓库。",
  "test_queries": [
    "推免 通知 截止日期 材料",
    "夏令营 报名 材料 学院",
    "预推免 面试 通知"
  ],
  "fallback": "保存 URL、标题和用户粘贴正文；字段缺失时进入 needs_review。",
  "output_scope": "workspace_or_fork"
}
```

## Notes

这个 connector 是字段映射和访问规则说明，不是通用爬虫实现。
