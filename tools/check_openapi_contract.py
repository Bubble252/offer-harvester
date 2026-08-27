from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "app" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from main import app  # noqa: E402

EXPECTED_TAGS = {
    "Application",
    "Profile",
    "Advisors and targets",
    "Materials",
    "Evidence and RAG",
    "Memory and feedback",
    "Workflow operations",
    "Skills",
    "Integrations",
}

REQUIRED_PATHS = {
    "/api/health",
    "/api/profile",
    "/api/advisors",
    "/api/targets",
    "/api/generated/{material_id}/download",
    "/api/rag/search",
    "/api/memory",
    "/api/skills",
    "/api/plugin/status",
}


def fail(message: str) -> None:
    raise SystemExit(f"OpenAPI contract failed: {message}")


def main() -> None:
    schema = app.openapi()
    info = schema.get("info", {})
    if info.get("title") != "Offer Harvester":
        fail(f"unexpected title: {info.get('title')!r}")
    if info.get("version") != "0.2.0-rc.1":
        fail(f"unexpected version: {info.get('version')!r}")

    actual_tags = {tag.get("name") for tag in schema.get("tags", [])}
    missing_tags = sorted(EXPECTED_TAGS - actual_tags)
    if missing_tags:
        fail(f"missing tags: {', '.join(missing_tags)}")

    paths = schema.get("paths", {})
    missing_paths = sorted(REQUIRED_PATHS - set(paths))
    if missing_paths:
        fail(f"missing required paths: {', '.join(missing_paths)}")

    for path, operations in paths.items():
        for method, operation in operations.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            if not operation.get("tags"):
                fail(f"{method.upper()} {path} has no category tag")
            if not operation.get("summary"):
                fail(f"{method.upper()} {path} has no summary")
            if not operation.get("responses"):
                fail(f"{method.upper()} {path} has no response contract")

    print(
        f"openapi contract passed: {len(paths)} paths, "
        f"{len(actual_tags)} tags, version {info['version']}"
    )


if __name__ == "__main__":
    main()
