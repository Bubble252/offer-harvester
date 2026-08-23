import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app" / "backend"))

from presentation_quality import precheck_reference_presentation  # noqa: E402

from integrations.presentation_engine.adapter import (  # noqa: E402
    LocalOutlineAdapter,
    LocalPptxAdapter,
    PresentationRequest,
)
from integrations.workflow_engine.adapter import WorkflowLogger  # noqa: E402


def test_local_presentation_adapter_has_a_safe_fallback(tmp_path):
    result = LocalOutlineAdapter().generate(
        PresentationRequest(
            title="张三/保研面试",
            outline="# 面试展示\n",
            output_dir=tmp_path,
        )
    )

    assert result.status == "fallback"
    assert result.output_path is not None
    assert result.output_path.exists()
    assert result.output_path.read_text(encoding="utf-8") == "# 面试展示\n"
    assert "/" not in result.output_path.name


def test_workflow_logger_keeps_structured_events():
    logger = WorkflowLogger()
    event = logger.record("profile_created", {"profile_id": "profile_demo"})

    assert event.event_type == "profile_created"
    assert event.payload["profile_id"] == "profile_demo"
    assert logger.events == [event]


def test_local_pptx_adapter_generates_five_editable_slides(tmp_path):
    outline = """# 5 分钟保研面试展示 PPT 大纲

## 1. 封面
- 标题：匿名学生

## 2. 教育背景
- 学校：某大学

## 3. 项目经历
- 项目：多模态问答

## 4. 方向匹配
- 导师方向：多模态学习

## 5. 未来计划
- 阅读课题组论文
"""
    result = LocalPptxAdapter().generate(
        PresentationRequest(title="匿名学生面试展示", outline=outline, output_dir=tmp_path)
    )

    assert result.status == "success"
    assert result.output_path is not None
    assert result.output_path.suffix == ".pptx"
    assert result.output_path.exists()

    from pptx import Presentation

    presentation = Presentation(str(result.output_path))
    assert len(presentation.slides) == 5
    assert presentation.slide_width > presentation.slide_height


def test_local_pptx_adapter_respects_requested_slide_count(tmp_path):
    outline = "\n".join(
        [
            "# 面试展示",
            *[f"\n## {index}. 页面 {index}\n- 内容 {index}\n" for index in range(1, 8)],
        ]
    )
    result = LocalPptxAdapter().generate(
        PresentationRequest(
            title="三页面试展示",
            outline=outline,
            output_dir=tmp_path,
            num_slides=3,
        )
    )

    from pptx import Presentation

    presentation = Presentation(str(result.output_path))
    assert len(presentation.slides) == 3


def test_reference_ppt_precheck_reports_functional_pages(tmp_path):
    result = LocalPptxAdapter().generate(
        PresentationRequest(
            title="参考模板",
            outline="# 参考模板\n\n## 1. 封面\n- 标题\n\n## 2. Agenda\n- 目录\n",
            output_dir=tmp_path,
            num_slides=2,
        )
    )

    report = precheck_reference_presentation(
        result.output_path,
        reference_id="ppt_ref_demo",
        filename="reference.pptx",
    )

    assert report.passed is True
    assert report.slide_count == 2
    assert report.functional_pages["opening"] is True
    assert report.fallback_allowed is True
