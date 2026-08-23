from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "evaluation_set"


def load_manifest() -> dict:
    return json.loads((FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8"))


def test_evaluation_set_has_expected_counts():
    manifest = load_manifest()
    assert manifest["rules"]["public_sources_only"] is True
    expected = {
        "teacher_pages": 5,
        "policy_pages": 5,
        "email_signals": 5,
        "student_profiles": 5,
    }
    for group, count in expected.items():
        items = manifest["items"][group]
        assert len(items) == count
        for item in items:
            path = FIXTURE_ROOT / item["path"]
            assert path.exists()
            assert item["valid_for_year"] == 2026
            assert item["fetched_at"].startswith("2026-")
            assert item["trusted"] is True


def test_evaluation_set_files_are_structured_and_anonymous():
    manifest = load_manifest()

    for item in manifest["items"]["teacher_pages"] + manifest["items"]["policy_pages"]:
        text = (FIXTURE_ROOT / item["path"]).read_text(encoding="utf-8")
        assert "source_kind:" in text
        assert "source_url:" in text
        assert "fetched_at:" in text
        assert "valid_for_year:" in text
        assert "真实" not in text
        assert "身份证" not in text

    for item in manifest["items"]["email_signals"]:
        text = (FIXTURE_ROOT / item["path"]).read_text(encoding="utf-8")
        assert "Subject:" in text
        assert "From:" in text
        assert "Date:" in text
        assert "@example.edu" in text

    for item in manifest["items"]["student_profiles"]:
        data = json.loads((FIXTURE_ROOT / item["path"]).read_text(encoding="utf-8"))
        assert data["name"].startswith("匿名学生")
        assert data["profile_id"].startswith("student_fixture_")
        assert isinstance(data["confirmation_map"], dict)
