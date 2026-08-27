from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app" / "backend"))

from skill_registry import get_skill_catalog_item  # noqa: E402

from tools.check_product_skill_standalone_ready import main as check_standalone_ready  # noqa: E402
from tools.plan_product_skill_export import build_plan  # noqa: E402

PRODUCT_SKILLS = (
    "contact-email-coach",
    "advisor-due-diligence",
    "recommendation-letter-helper",
)


def test_product_skills_are_standalone_ready_by_contract():
    check_standalone_ready()


def test_manifest_preserves_main_repo_incubation_boundary():
    for skill_id in PRODUCT_SKILLS:
        item = get_skill_catalog_item(skill_id)
        skill_dir = ROOT / item["path"]
        manifest = json.loads((skill_dir / "skill.manifest.json").read_text(encoding="utf-8"))

        assert item["maturity"] == "incubating"
        assert item["standalone_status"] == "requires_offer_harvester_control_plane"
        assert manifest["maturity"] == "standalone-ready-incubating"
        assert manifest["standalone_readiness"]["ready_to_extract"] is True
        assert manifest["standalone_readiness"]["requires_adapter_stub"] is True
        assert "Offer Harvester FastAPI control plane" in manifest["host_dependencies"]
        assert "candidate_execution" in manifest["state_writes"]
        forbidden = manifest["forbidden_capabilities"]
        assert any(
            marker in capability
            for capability in forbidden
            for marker in ("send", "submit", "contact", "impersonate")
        )


def test_product_skill_export_plan_is_manifest_bound():
    for skill_id in PRODUCT_SKILLS:
        plan = build_plan(skill_id)

        assert plan["skill_id"] == skill_id
        assert plan["maturity"] == "standalone-ready-incubating"
        assert plan["standalone_status"] == "requires_offer_harvester_control_plane"
        assert plan["file_count"] >= 9
        assert "SKILL.md" in plan["files"]
        assert "skill.manifest.json" in plan["files"]
        assert "schemas/input.schema.json" in plan["files"]
        assert "schemas/output.schema.json" in plan["files"]
        assert sum(path.startswith("fixtures/") for path in plan["files"]) >= 3
        assert all(not path.startswith("../") for path in plan["files"])
