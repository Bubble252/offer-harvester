from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from skill_registry import get_skill_catalog_item, list_skill_catalog  # noqa: E402

PRODUCT_SKILLS = {
    "contact-email-coach": {
        "documentation": "docs/guides/skills/contact-email-coach.md",
        "dsh_tool": "offer_harvester_draft_contact_email",
    },
    "advisor-due-diligence": {
        "documentation": "docs/guides/skills/advisor-due-diligence.md",
        "dsh_tool": "offer_harvester_advisor_due_diligence",
    },
    "recommendation-letter-helper": {
        "documentation": "docs/guides/skills/recommendation-letter-helper.md",
        "dsh_tool": "offer_harvester_recommendation_letter_helper",
    },
}


def chinese_pair(path: Path) -> Path:
    return path.with_name(f"{path.stem}.zh-CN{path.suffix}")


def test_product_skill_catalog_has_public_discovery_contract():
    products = {item["skill_id"]: item for item in list_skill_catalog(category="product")}
    assert set(PRODUCT_SKILLS) <= set(products)

    frontend = (ROOT / "app" / "frontend" / "index.html").read_text(encoding="utf-8")
    dsh_plugin = (ROOT / "integrations" / "deepseek_harness" / "src" / "plugin.ts").read_text(
        encoding="utf-8"
    )

    for skill_id, expected in PRODUCT_SKILLS.items():
        item = products[skill_id]
        assert item["no_send"] is True
        assert item["write_permissions"] == ["candidate_execution"]
        assert item["maturity"] == "incubating"
        assert item["standalone_status"] == "requires_offer_harvester_control_plane"
        assert item["ui_entry"] == f"skill_lab:{skill_id}"
        assert item["dsh_tool"] == expected["dsh_tool"]
        assert item["documentation"] == expected["documentation"]
        assert item["manifest"] == f"skills/{skill_id}/skill.manifest.json"

        for field in (
            "display_name",
            "display_name_zh",
            "short_description",
            "short_description_zh",
            "input_summary",
            "input_summary_zh",
            "output_summary",
            "output_summary_zh",
        ):
            assert item[field]

        documentation = ROOT / item["documentation"]
        assert documentation.exists()
        assert (ROOT / item["manifest"]).exists()
        assert chinese_pair(documentation).exists()
        assert f'data-skill-form="{skill_id}"' in frontend
        assert item["dsh_tool"] in dsh_plugin


def test_product_skill_examples_are_synthetic_and_traceable():
    for skill_id in PRODUCT_SKILLS:
        item = get_skill_catalog_item(skill_id)
        skill_dir = ROOT / item["path"]
        example = skill_dir / "examples" / "minimal-input.json"
        expected_output = skill_dir / "examples" / "expected-output.md"

        payload = json.loads(example.read_text(encoding="utf-8"))
        assert payload["example_kind"] == "synthetic_product_skill_input"
        assert payload["synthetic"] is True
        assert payload["skill_id"] == skill_id
        assert "resolved_context" in payload

        output_text = expected_output.read_text(encoding="utf-8").lower()
        assert "candidate-only" in output_text
        assert "no-send" in output_text


def test_product_skill_guides_are_linked_from_public_skill_docs():
    english = (ROOT / "docs" / "guides" / "skills.md").read_text(encoding="utf-8")
    chinese = (ROOT / "docs" / "guides" / "skills.zh-CN.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_zh = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    skills_readme = (ROOT / "skills" / "README.md").read_text(encoding="utf-8")
    skills_readme_zh = (ROOT / "skills" / "README.zh-CN.md").read_text(encoding="utf-8")

    for skill_id, expected in PRODUCT_SKILLS.items():
        guide_path = expected["documentation"][len("docs/guides/") :]
        assert guide_path in english
        assert skill_id in chinese
        assert expected["documentation"] in readme
        assert expected["documentation"].replace(".md", ".zh-CN.md") in readme_zh
        assert f"../{expected['documentation']}" in skills_readme
        assert f"../{expected['documentation'].replace('.md', '.zh-CN.md')}" in skills_readme_zh
