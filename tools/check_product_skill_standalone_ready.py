from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_SKILLS = {
    "contact-email-coach",
    "advisor-due-diligence",
    "recommendation-letter-helper",
}
REQUIRED_MANIFEST_FIELDS = {
    "schema_version",
    "skill_id",
    "package_name",
    "version",
    "maturity",
    "entrypoints",
    "paths",
    "host_dependencies",
    "state_writes",
    "forbidden_capabilities",
    "privacy_boundary",
    "standalone_readiness",
}
REQUIRED_PATH_KEYS = {
    "skill",
    "agent_metadata",
    "contract",
    "input_schema",
    "output_schema",
    "fixtures",
}
FORBIDDEN_FIXTURE_PATTERNS = {
    "real-looking email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "web url": re.compile(r"https?://", re.IGNORECASE),
    "api key": re.compile(r"\b(sk-[A-Za-z0-9_-]{12,}|api[_-]?key)\b", re.IGNORECASE),
}


def fail(message: str) -> None:
    print(f"standalone readiness check failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        fail(f"missing file: {path.relative_to(ROOT)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {path.relative_to(ROOT)}: {exc}")


def require_fields(data: dict[str, Any], fields: set[str], label: str) -> None:
    missing = sorted(field for field in fields if field not in data)
    if missing:
        fail(f"{label} missing fields: {', '.join(missing)}")


def check_no_private_fixture_content(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for label, pattern in FORBIDDEN_FIXTURE_PATTERNS.items():
        if pattern.search(text):
            fail(f"{path.relative_to(ROOT)} contains forbidden {label}")


def check_schema(path: Path, expected_title: str) -> None:
    schema = load_json(path)
    if schema.get("title") != expected_title:
        fail(f"{path.relative_to(ROOT)} has unexpected title")
    if schema.get("type") != "object":
        fail(f"{path.relative_to(ROOT)} must define an object schema")
    if "required" not in schema or "properties" not in schema:
        fail(f"{path.relative_to(ROOT)} must define required fields and properties")


def check_fixture(skill_id: str, path: Path) -> None:
    check_no_private_fixture_content(path)
    fixture = load_json(path)
    if fixture.get("fixture_kind") != "synthetic_product_skill_contract":
        fail(f"{path.relative_to(ROOT)} has wrong fixture_kind")
    if fixture.get("synthetic") is not True:
        fail(f"{path.relative_to(ROOT)} must be marked synthetic")
    if fixture.get("skill_id") != skill_id:
        fail(f"{path.relative_to(ROOT)} skill_id mismatch")
    if not isinstance(fixture.get("input"), dict):
        fail(f"{path.relative_to(ROOT)} must include input object")
    expected = fixture.get("expected_output")
    if not isinstance(expected, dict):
        fail(f"{path.relative_to(ROOT)} must include expected_output object")
    if expected.get("skill_id") != skill_id:
        fail(f"{path.relative_to(ROOT)} expected_output skill_id mismatch")
    if expected.get("no_send") is not True:
        fail(f"{path.relative_to(ROOT)} expected_output must be no_send")
    if expected.get("requires_user_confirmation") is not True:
        fail(f"{path.relative_to(ROOT)} expected_output must require user confirmation")
    if expected.get("candidate_status") not in {"candidate", "needs_review", "blocked"}:
        fail(f"{path.relative_to(ROOT)} expected_output has invalid candidate_status")


def check_skill(skill_id: str, catalog_item: dict[str, Any]) -> None:
    skill_dir = ROOT / str(catalog_item["path"])
    if (skill_dir / "README.md").exists():
        fail(f"{skill_id} must not keep README.md inside the skill package")

    manifest = load_json(skill_dir / "skill.manifest.json")
    require_fields(manifest, REQUIRED_MANIFEST_FIELDS, f"{skill_id} manifest")
    if manifest.get("skill_id") != skill_id:
        fail(f"{skill_id} manifest skill_id mismatch")
    if manifest.get("maturity") != "standalone-ready-incubating":
        fail(f"{skill_id} manifest maturity must be standalone-ready-incubating")
    if manifest.get("entrypoints", {}).get("skill_lab") != catalog_item.get("ui_entry"):
        fail(f"{skill_id} manifest Skill Lab entry does not match catalog")
    if manifest.get("entrypoints", {}).get("dsh_tool") != catalog_item.get("dsh_tool"):
        fail(f"{skill_id} manifest DSH tool does not match catalog")
    if manifest.get("state_writes") != ["candidate_execution", "agent_run", "workflow_event"]:
        fail(f"{skill_id} manifest has unsafe state_writes")
    if not manifest.get("standalone_readiness", {}).get("ready_to_extract"):
        fail(f"{skill_id} manifest must be ready_to_extract")
    if not manifest.get("standalone_readiness", {}).get("requires_adapter_stub"):
        fail(f"{skill_id} manifest must require adapter stub")

    paths = manifest.get("paths", {})
    require_fields(paths, REQUIRED_PATH_KEYS, f"{skill_id} manifest paths")
    for key in REQUIRED_PATH_KEYS - {"fixtures"}:
        target = skill_dir / str(paths[key])
        if not target.exists():
            fail(f"{skill_id} manifest path missing: {key}")

    check_schema(skill_dir / str(paths["input_schema"]), f"{manifest['display_name']} Input")
    check_schema(skill_dir / str(paths["output_schema"]), f"{manifest['display_name']} Output")

    fixture_dir = skill_dir / str(paths["fixtures"])
    fixtures = sorted(fixture_dir.glob("*.json"))
    if len(fixtures) < 3:
        fail(f"{skill_id} must have at least three standalone fixtures")
    statuses = set()
    for fixture_path in fixtures:
        check_fixture(skill_id, fixture_path)
        statuses.add(load_json(fixture_path)["expected_output"]["candidate_status"])
    if not {"candidate", "needs_review", "blocked"} <= statuses:
        fail(f"{skill_id} fixtures must cover candidate, needs_review, and blocked")


def main() -> None:
    catalog = load_json(ROOT / "skills" / "catalog.json")
    entries = {item.get("skill_id"): item for item in catalog.get("skills", [])}
    missing = sorted(PRODUCT_SKILLS - set(entries))
    if missing:
        fail(f"catalog missing product skills: {', '.join(missing)}")
    for skill_id in sorted(PRODUCT_SKILLS):
        item = entries[skill_id]
        if item.get("maturity") != "incubating":
            fail(f"{skill_id} catalog maturity must remain incubating")
        if item.get("standalone_status") != "requires_offer_harvester_control_plane":
            fail(f"{skill_id} catalog standalone status must preserve control-plane boundary")
        if not item.get("manifest"):
            fail(f"{skill_id} catalog must point to a manifest")
        check_skill(skill_id, item)
    print("product skill standalone readiness check passed")


if __name__ == "__main__":
    main()
