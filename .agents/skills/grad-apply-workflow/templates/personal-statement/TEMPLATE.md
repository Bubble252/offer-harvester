# 个人陈述模板

```json
{
  "template_id": "personal_statement_default_zh",
  "name": "中文个人陈述默认模板",
  "template_type": "personal_statement",
  "version": "0.1.0",
  "description": "用于组织保研个人陈述初稿结构，强调动机、经历、能力证据和目标匹配。",
  "variables": [
    "student_alias",
    "academic_background",
    "research_interest",
    "representative_project",
    "project_contribution",
    "target_program",
    "future_plan"
  ],
  "sample_context": {
    "student_alias": "匿名申请者",
    "academic_background": "计算机相关专业学习经历",
    "research_interest": "智能系统与可信机器学习",
    "representative_project": "科研问答系统项目",
    "project_contribution": "负责问题建模、检索流程设计和结果分析",
    "target_program": "样例项目",
    "future_plan": "继续围绕可解释、可靠的智能系统开展训练"
  },
  "applicable_scenarios": [
    "个人陈述初稿",
    "申请摘要扩写",
    "材料审计前的结构化草稿"
  ],
  "style_rules": [
    "先写动机和背景，再写证据化经历，最后写目标匹配",
    "避免空泛形容词堆叠",
    "每段只承载一个核心论点"
  ],
  "privacy_rules": [
    "模板内不包含真实姓名、联系方式、成绩或排名",
    "项目细节通过变量注入，且必须保留用户确认状态",
    "不直接承诺研究成果或录取结果"
  ],
  "validation_methods": [
    "manifest_required_keys",
    "variable_completeness",
    "sample_render",
    "privacy_literal_scan"
  ],
  "managed_block": "grad_apply.personal_statement.default_zh"
}
```

```template
# 个人陈述草稿

我是{{student_alias}}，本科阶段主要围绕{{academic_background}}展开学习和训练。随着课程学习和项目实践深入，我逐渐形成了对{{research_interest}}方向的持续兴趣。

在{{representative_project}}中，我主要{{project_contribution}}。这段经历让我意识到，可靠的研究工作需要清楚的问题定义、可复核的实验过程，以及对失败案例的持续分析。

我申请{{target_program}}，希望在已有基础上继续推进{{future_plan}}。后续我也会根据导师方向和项目要求，补充更具体的论文阅读、项目复盘和面试准备材料。
```
