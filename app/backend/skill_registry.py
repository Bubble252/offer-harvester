"""Portable Skill catalog discovery for the Offer Harvester control plane."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = PROJECT_ROOT / "skills" / "catalog.json"


def load_skill_catalog() -> Dict[str, Any]:
    if not CATALOG_PATH.exists():
        return {"schema_version": "1.0", "catalog_version": "", "skills": []}
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    skills = payload.get("skills", [])
    if not isinstance(skills, list):
        raise ValueError("Skill catalog must contain a skills array")
    for item in skills:
        _validate_item(item)
    return payload


def list_skill_catalog(category: str = "") -> List[Dict[str, Any]]:
    skills = load_skill_catalog().get("skills", [])
    if category:
        skills = [item for item in skills if item.get("category") == category]
    return skills


def get_skill_catalog_item(skill_id: str) -> Dict[str, Any]:
    for item in list_skill_catalog():
        if item.get("skill_id") == skill_id:
            return item
    raise KeyError(skill_id)


def _validate_item(item: Dict[str, Any]) -> None:
    required = {
        "skill_id",
        "category",
        "status",
        "version",
        "path",
        "no_send",
        "write_permissions",
        "source_policy",
        "private_data_policy",
        "status_truth_source",
    }
    missing = sorted(field for field in required if field not in item)
    if missing:
        raise ValueError(f"Skill catalog entry missing: {', '.join(missing)}")
    skill_dir = PROJECT_ROOT / str(item["path"])
    if not (skill_dir / "SKILL.md").exists():
        raise ValueError(f"Skill catalog entry has no SKILL.md: {item['skill_id']}")
