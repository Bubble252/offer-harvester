# 导师主页 Connector

```json
{
  "connector_id": "advisor_homepage_generic_zh",
  "name": "中文导师主页通用映射",
  "source_type": "advisor_homepage",
  "version": "0.1.0",
  "description": "用于描述导师主页、教师主页或实验室个人页如何映射到 AdvisorProfile 字段。",
  "url_patterns": [
    "https://*/info/*",
    "https://*/faculty/*",
    "https://*/teacher/*",
    "https://*/people/*",
    "https://*/~*"
  ],
  "field_mapping": {
    "title": "页面标题或导师姓名标题",
    "source_url": "导师主页 URL",
    "raw_text": "页面正文文本",
    "name_zh": "中文姓名",
    "name_en": "英文姓名",
    "school": "学校",
    "college": "学院或系所",
    "lab_name": "实验室名称",
    "email": "公开邮箱",
    "research_directions": "研究方向",
    "representative_papers": "代表论文",
    "admission_requirements": "招生要求",
    "recruiting_status": "招生状态"
  },
  "access_rules": [
    "仅访问公开导师主页或学校教师主页",
    "不访问登录后通讯录、内部系统或验证码页面",
    "公开邮箱只用于用户人工联系，不自动发信",
    "抓取失败时保留失败原因并提示手动粘贴正文"
  ],
  "robots_policy": "如果 robots.txt 或页面说明禁止自动访问，则不执行自动抓取，只允许用户手动粘贴。",
  "tos_policy": "遵守学校和实验室网站使用条款；connector 输出只进入用户 workspace 或 fork。",
  "test_queries": [
    "导师 姓名 研究方向 邮箱",
    "教授 招生 硕士 直博",
    "实验室 代表论文 项目"
  ],
  "test_urls": [
    "https://air.tsinghua.edu.cn/info/1046/1201.htm"
  ],
  "fallback": "保存 URL、抓取失败原因和手动粘贴正文；无法确认身份时 identity_confirmed=false。",
  "output_scope": "workspace_or_fork"
}
```

## Notes

这个 connector 只定义字段映射、访问规则和失败兜底。真实读取仍由后端受控服务执行。
