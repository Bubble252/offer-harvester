from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

import main as backend_main  # noqa: E402
from models import AdvisorProfile, AdvisorSource, Target  # noqa: E402
from plugin_auth import require_plugin_scope  # noqa: E402
from services import build_profile_from_text  # noqa: E402
from skill_execution import (  # noqa: E402
    MaterialAuditRequest,
    SkillExecutionRequest,
    execute_material_audit,
    execute_product_skill,
)
from skill_registry import list_skill_catalog  # noqa: E402
from storage import Workspace  # noqa: E402


def _context(workspace: Workspace):
    profile = build_profile_from_text(
        "匿名学生\n某大学计算机学院\n项目：检索增强问答系统\n技能：Python, FastAPI",
        source_document_ids=["doc_demo"],
    )
    profile.confirmation_map["projects"] = "confirmed"
    source = AdvisorSource(
        source_type="manual_text",
        title="合成导师主页",
        raw_text="合成导师研究方向为检索增强生成。",
        cleaned_text="合成导师研究方向为检索增强生成。",
        trusted=True,
    )
    advisor = AdvisorProfile(
        name_zh="合成导师",
        school="合成大学",
        research_directions=["检索增强生成"],
        identity_confirmed=True,
        source_ids=[source.source_id],
        evidence_map={"research_directions": [source.source_id]},
    )
    target = Target(
        name="合成大学合成导师课题组",
        advisor_id=advisor.advisor_id,
        source_ids=[source.source_id],
    )
    workspace.write("profiles", _dump(profile), "profile_id")
    workspace.write("advisor_sources", _dump(source), "source_id")
    workspace.write("advisors", _dump(advisor), "advisor_id")
    workspace.write("targets", _dump(target), "target_id")
    return profile, target, advisor


def _dump(value):
    return value.model_dump() if hasattr(value, "model_dump") else value.dict()


def _request(host: str, headers: dict[str, str] | None = None) -> Request:
    encoded_headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]
    return Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "http",
            "path": "/api/plugin/skills/contact-email-coach/run",
            "headers": encoded_headers,
            "client": (host, 12345),
        }
    )


def test_skill_catalog_has_portable_and_product_entries():
    items = list_skill_catalog()
    assert {item["skill_id"] for item in items} >= {
        "evidence-claim-audit",
        "source-connector-authoring",
        "profile-field-normalization",
        "contact-email-coach",
        "advisor-due-diligence",
        "recommendation-letter-helper",
    }
    assert all(item["no_send"] is True for item in items)


def test_contact_email_skill_runs_existing_agent_chain_as_candidate(tmp_path):
    workspace = Workspace(str(tmp_path))
    profile, target, advisor = _context(workspace)

    result = execute_product_skill(
        "contact-email-coach",
        SkillExecutionRequest(target_id=target.target_id, mode="new"),
        workspace=workspace,
        profile=profile,
        target=target,
        advisor=advisor,
        match=None,
    )

    assert result.no_send is True
    assert result.requires_user_confirmation is True
    assert result.output["material"]["material_type"] == "contact_email"
    assert result.output["evidence_audit"]["auditor"] == "EvidenceAuditAgent"
    assert workspace.read("skill_executions", result.execution_id)
    assert workspace.read("agent_runs", result.agent_run.run_id)


def test_advisor_and_recommendation_skills_keep_candidate_boundary(tmp_path):
    workspace = Workspace(str(tmp_path))
    profile, target, advisor = _context(workspace)
    profile.confirmation_map["skills"] = "rejected"

    diligence = execute_product_skill(
        "advisor-due-diligence",
        SkillExecutionRequest(advisor_id=advisor.advisor_id, target_id=target.target_id),
        workspace=workspace,
        profile=profile,
        target=target,
        advisor=advisor,
        match=None,
    )
    recommendation = execute_product_skill(
        "recommendation-letter-helper",
        SkillExecutionRequest(
            target_id=target.target_id,
            recommender_name="示例老师",
            relationship="课程教师",
        ),
        workspace=workspace,
        profile=profile,
        target=target,
        advisor=advisor,
        match=None,
    )

    assert diligence.candidate_status in {"candidate", "needs_review"}
    assert "risk_signal_policy" in diligence.output
    assert recommendation.no_send is True
    assert "Python" not in recommendation.output["material"]["content"]
    assert "不能冒充推荐人提交" in recommendation.output["material"]["content"]
    assert recommendation.agent_run is not None
    assert workspace.read("agent_runs", recommendation.agent_run.run_id)
    assert recommendation.events[-1].event_type == "final_saved"


def test_material_audit_is_traceable_and_does_not_mutate_material(tmp_path):
    workspace = Workspace(str(tmp_path))
    profile, target, advisor = _context(workspace)
    material = {
        "material_id": "mat_audit_demo",
        "target_id": target.target_id,
        "material_type": "contact_email",
        "title": "审计样本",
        "content": "老师您好。我有检索增强问答系统项目，想申请您的检索增强生成方向。",
        "evidence": [profile.profile_id, advisor.source_ids[0]],
    }
    workspace.write("generated", material, "material_id")

    result = execute_material_audit(
        MaterialAuditRequest(material_id=material["material_id"]),
        workspace=workspace,
        profile=profile,
    )

    assert result.skill_id == "evidence-claim-audit"
    assert result.no_send is True
    assert result.output["material"]["content"] == material["content"]
    assert result.output["mutation_policy"].endswith("source material.")
    assert workspace.read("generated", material["material_id"]) == material
    assert result.agent_run is not None


def test_remote_plugin_requires_token_and_scope(monkeypatch):
    monkeypatch.setenv("OFFER_HARVESTER_PLUGIN_AUTH_MODE", "token")
    monkeypatch.setenv("OFFER_HARVESTER_PLUGIN_TOKEN", "demo-plugin-token")
    monkeypatch.setenv("OFFER_HARVESTER_PLUGIN_SCOPES", "skill:run")

    with pytest.raises(HTTPException) as exc_info:
        require_plugin_scope(_request("198.51.100.9"), "skill:run")
    assert exc_info.value.status_code == 401

    require_plugin_scope(
        _request(
            "198.51.100.9",
            {
                "X-Offer-Harvester-Plugin-Token": "demo-plugin-token",
                "X-Offer-Harvester-Plugin-Scopes": "skill:run",
            },
        ),
        "skill:run",
    )

    with pytest.raises(HTTPException) as exc_info:
        require_plugin_scope(
            _request(
                "198.51.100.9",
                {
                    "X-Offer-Harvester-Plugin-Token": "demo-plugin-token",
                    "X-Offer-Harvester-Plugin-Scopes": "skill:run",
                },
            ),
            "advisor:report",
        )
    assert exc_info.value.status_code == 403


def test_skill_and_plugin_routes_are_exposed():
    routes = {route.path for route in backend_main.app.routes}
    assert "/api/skills" in routes
    assert "/api/skills/{skill_id}/run" in routes
    assert "/api/plugin/skills/{skill_id}/run" in routes
    assert "/api/plugin/materials/audit" in routes
