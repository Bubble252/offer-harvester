from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app" / "backend"))

from main import app, index, list_skills, plugin_status  # noqa: E402


def test_public_demo_smoke_contract():
    home = index()
    assert home.path.name == "index.html"
    assert "Offer Harvester" in Path(home.path).read_text(encoding="utf-8")

    schema = app.openapi()
    assert schema["info"]["version"] == "0.2.0-rc.1"

    skills = list_skills()
    assert len(skills["skills"]) >= 6

    plugin = plugin_status()
    assert "plugin_auth_mode" in plugin


def test_public_app_metadata_and_openapi_categories():
    schema = app.openapi()

    assert schema["info"]["title"] == "Offer Harvester"
    assert schema["info"]["version"] == "0.2.0-rc.1"
    assert "/api/skills" in schema["paths"]
    assert "/api/plugin/status" in schema["paths"]
    assert "/api/rag/search" in schema["paths"]

    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            if method in {"get", "post", "put", "patch", "delete"}:
                assert operation["tags"], (method, path)
                assert operation["summary"], (method, path)
                assert operation["responses"], (method, path)


def test_public_documentation_entries_exist():
    expected = [
        "README.md",
        "README.zh-CN.md",
        "docs/README.md",
        "docs/README.zh-CN.md",
        "docs/getting-started.md",
        "docs/getting-started.zh-CN.md",
        "docs/architecture.md",
        "docs/architecture.zh-CN.md",
        "docs/reference/api.md",
        "docs/reference/api.zh-CN.md",
        "docs/reference/configuration.md",
        "docs/reference/configuration.zh-CN.md",
        "docs/operations/release.md",
        "docs/operations/release.zh-CN.md",
    ]
    assert all((ROOT / relative).exists() for relative in expected)
