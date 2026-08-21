# 数据 Schema 初稿

## 设计原则

第一版主要服务保研中的硕博申请，数据模型围绕“真实导师信息 + 学生真实经历 + 稳妥匹配证据”设计。

设计原则：

- 中文材料优先，字段命名使用英文，展示文案使用中文
- 导师信息必须可追溯到真实来源
- URL 抓取失败时必须支持手动粘贴兜底
- 模型生成内容不能覆盖原始事实，只能生成结构化摘要和建议
- 所有匹配结论都需要 evidence 证据链

## User Document Manifest：用户原始资料索引

用于记录用户上传或粘贴的原始学生资料。原始资料保存在 `workspace/user_documents/`，结构化画像保存在 `workspace/profiles/`，二者不能混用。

```json
{
  "documents": [
    {
      "document_id": "doc_001",
      "category": "resumes",
      "path": "user_documents/resumes/resume_20260821_abcd1234ef.txt",
      "original_filename": "resume.txt",
      "source_type": "local_upload",
      "content_hash": "sha256:...",
      "uploaded_at": "2026-08-21T10:00:00+08:00",
      "trusted": true,
      "confirmed": false,
      "notes": "学生资料页上传文件"
    }
  ]
}
```

字段说明：

- `category`：`resumes`、`transcripts`、`research_projects`、`publications`、`awards`、`personal_statements`、`manual_inputs`、`web_supplements`、`misc`
- `source_type`：`local_upload`、`manual_input`、`web_supplement`
- `path`：相对 `workspace/` 的路径，Agent 不应绕过 manifest 随意扫描目录
- `content_hash`：用于去重、审计和判断资料是否被替换
- `confirmed`：是否已被用户确认可以进入正式学生画像

## Student Profile：学生结构化画像

用于存储从用户原始资料中抽取的学生画像。第一版字段级证据映射记录每类字段来自哪些 `document_id`，后续再扩展到逐条项目和逐条论文级别。

```json
{
  "profile_id": "profile_001",
  "name": "匿名学生",
  "education": "某大学计算机学院",
  "gpa": "3.85/4.00",
  "rank": "前 10%",
  "research_interests": ["多模态", "智能体"],
  "projects": ["项目：多模态论文问答系统"],
  "publications": ["论文：某会议在投"],
  "competitions": ["大学生创新训练计划"],
  "skills": ["Python", "PyTorch"],
  "risks": [],
  "source_document_ids": ["doc_resume", "doc_project"],
  "evidence_map": {
    "education": ["doc_resume"],
    "gpa": ["doc_resume"],
    "rank": ["doc_resume"],
    "projects": ["doc_project"],
    "publications": ["doc_project"],
    "skills": ["doc_resume", "doc_project"]
  },
  "updated_at": "2026-08-21T10:00:00+08:00"
}
```

字段说明：

- `source_document_ids`：本次画像抽取使用过的原始资料 ID 集合
- `evidence_map`：字段级证据映射，值必须来自 `User Document Manifest`
- `raw_text`：后端可保存用于本地复核，但开源样例不应包含真实学生隐私

## Advisor Source：导师资料来源

用于记录每一条导师相关资料的来源。来源可以是 URL 抓取，也可以是用户手动粘贴。

```json
{
  "source_id": "src_001",
  "target_id": "target_001",
  "source_type": "advisor_homepage",
  "url": "https://example.edu/faculty/name",
  "title": "某某教授 - 学院教师主页",
  "fetch_status": "success",
  "fetched_at": "2026-08-16T10:00:00+08:00",
  "content_hash": "sha256:...",
  "raw_text": "网页正文或用户粘贴文本",
  "cleaned_text": "清洗后的正文",
  "language": "zh",
  "trusted": true,
  "notes": ""
}
```

字段说明：

- `source_type`：`advisor_homepage`、`lab_homepage`、`admission_notice`、`publication_page`、`manual_text`、`school_profile`、`other`
- `fetch_status`：`success`、`failed`、`manual`
- `raw_text`：保留原始文本，方便复核
- `cleaned_text`：用于 LLM 解析的清洗文本
- `trusted`：用户或系统标记该来源是否可靠

## Advisor Profile：导师结构化信息

用于存储从真实来源中解析出的导师画像。

```json
{
  "advisor_id": "advisor_001",
  "name_zh": "张三",
  "name_en": "San Zhang",
  "title": "教授",
  "school": "某某大学",
  "college": "计算机科学与技术学院",
  "department": "人工智能系",
  "lab_name": "智能系统实验室",
  "homepage_url": "https://example.edu/faculty/name",
  "email": "name@example.edu",
  "office": "",
  "research_directions": [
    "大模型推理",
    "多模态学习",
    "智能体系统"
  ],
  "recent_focus": [
    "面向复杂任务的多智能体协作",
    "视觉语言模型的可靠性评估"
  ],
  "keywords": [
    "LLM",
    "multimodal learning",
    "agent"
  ],
  "recruiting_status": "unknown",
  "student_type": ["master", "phd", "direct_phd"],
  "source_ids": ["src_001", "src_002"],
  "last_verified_at": "2026-08-16T10:00:00+08:00"
}
```

字段说明：

- `recruiting_status`：`open`、`closed`、`unknown`
- `student_type`：`master`、`phd`、`direct_phd`
- `recent_focus` 必须从主页、招生说明或论文中提取，不允许凭空推断

## Program Target：保研目标

用于表示一个具体申请目标。一个目标可以绑定一个导师，也可以是实验室或项目。

```json
{
  "target_id": "target_001",
  "target_type": "advisor",
  "name": "某某大学计算机学院张三教授课题组",
  "advisor_id": "advisor_001",
  "school": "某某大学",
  "college": "计算机科学与技术学院",
  "program_name": "2026 年优秀大学生夏令营",
  "degree_track": "direct_phd",
  "application_round": "summer_camp",
  "deadline": "2026-06-20",
  "contact_required": true,
  "materials_required": [
    "中文简历",
    "成绩单",
    "科研项目介绍",
    "个人陈述"
  ],
  "status": "researching",
  "priority": "medium",
  "source_ids": ["src_001", "src_003"]
}
```

字段说明：

- `target_type`：`advisor`、`lab`、`program`
- `degree_track`：`master`、`phd`、`direct_phd`、`unknown`
- `application_round`：`summer_camp`、`pre_recommendation`、`final_recommendation`、`other`
- `priority`：`high`、`medium`、`low`

## Publication Item：论文与近期方向

用于记录导师近期论文，支持匹配学生科研方向。

```json
{
  "publication_id": "pub_001",
  "advisor_id": "advisor_001",
  "title": "A Survey on Multimodal Agents",
  "year": 2026,
  "venue": "arXiv",
  "authors": ["San Zhang", "Li Wang"],
  "url": "https://arxiv.org/abs/xxxx.xxxxx",
  "abstract": "",
  "keywords": ["multimodal agent", "LLM"],
  "source_id": "src_004",
  "relevance_note": "与学生的多模态项目相关"
}
```

MVP 可以先不做完整论文爬取，但 schema 需要保留该结构，方便后续扩展。

## Match Report：匹配分析结果

用于存储学生与导师/项目的匹配结论。

```json
{
  "match_id": "match_001",
  "profile_id": "profile_001",
  "target_id": "target_001",
  "fit_score": 82,
  "tier": "reasonable_fit",
  "summary": "学生的多模态项目与导师近期方向相关，但论文成果不足，建议作为稳妥偏冲刺目标。",
  "strengths": [
    {
      "point": "有多模态项目经历",
      "student_evidence_ids": ["proj_001"],
      "advisor_evidence_ids": ["src_001", "pub_001"]
    }
  ],
  "gaps": [
    {
      "point": "缺少正式论文发表",
      "severity": "medium",
      "suggestion": "在材料中强调项目复现、实验设计和可解释贡献"
    }
  ],
  "recommended_actions": [
    "优先准备一页科研项目摘要",
    "套磁邮件中突出多模态项目与导师近期方向的关系"
  ],
  "created_at": "2026-08-16T10:00:00+08:00"
}
```

字段说明：

- `tier`：`strong_fit`、`reasonable_fit`、`weak_fit`、`unknown`
- `student_evidence_ids`：指向学生资料中的项目、论文、竞赛、课程等证据
- `advisor_evidence_ids`：指向导师来源、论文或招生要求证据

## Application Tracker：申请状态

用于记录申请进度。

```json
{
  "application_id": "app_001",
  "target_id": "target_001",
  "status": "contacted",
  "deadline": "2026-06-20",
  "last_contact_at": "2026-05-28",
  "next_action": "等待导师回复，7 天后准备二次跟进",
  "materials": [
    {
      "material_type": "contact_email",
      "path": "workspace/generated/app_001/contact_email.md",
      "status": "drafted"
    },
    {
      "material_type": "interview_ppt",
      "path": "workspace/generated/app_001/interview_intro.pptx",
      "status": "generated"
    }
  ],
  "notes": []
}
```

状态枚举：

```text
draft
researching
ready_to_contact
contacted
replied
materials_preparing
submitted
shortlisted
interview_scheduled
interview_done
accepted
rejected
withdrawn
```

## 中文优先策略

MVP 默认生成中文材料：

- 中文套磁邮件
- 中文个人陈述大纲
- 中文研究计划大纲
- 中文科研项目介绍
- 中文面试展示 PPT
- 中文模拟面试题

英文材料保留扩展接口：

- 英文 CV
- 英文套磁邮件
- 英文自我介绍
- 英文 PhD interview slides
