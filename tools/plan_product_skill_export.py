from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    print(f"product skill export plan failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        fail(f"missing file: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def product_items() -> dict[str, dict[str, Any]]:
    catalog = load_json(ROOT / "skills" / "catalog.json")
    return {
        item["skill_id"]: item
        for item in catalog.get("skills", [])
        if item.get("category") == "product"
    }


def resolve_package_files(skill_dir: Path, manifest: dict[str, Any]) -> list[Path]:
    paths = manifest.get("paths", {})
    package_files: list[Path] = [skill_dir / "skill.manifest.json"]
    for key, relative in paths.items():
        target = (skill_dir / str(relative)).resolve()
        if not str(target).startswith(str(skill_dir.resolve())):
            fail(f"{manifest['skill_id']} path escapes skill directory: {relative}")
        if key == "fixtures":
            package_files.extend(sorted(target.glob("*.json")))
        elif target.is_file():
            package_files.append(target)
        else:
            fail(f"{manifest['skill_id']} export path is not a file: {relative}")
    return sorted(set(package_files))


def build_plan(skill_id: str) -> dict[str, Any]:
    items = product_items()
    if skill_id not in items:
        fail(f"unknown product skill: {skill_id}")
    item = items[skill_id]
    manifest = load_json(ROOT / str(item["manifest"]))
    skill_dir = (ROOT / str(item["path"])).resolve()
    files = resolve_package_files(skill_dir, manifest)
    return {
        "skill_id": skill_id,
        "package_name": manifest["package_name"],
        "version": manifest["version"],
        "maturity": manifest["maturity"],
        "standalone_status": item["standalone_status"],
        "file_count": len(files),
        "files": [str(path.relative_to(skill_dir)) for path in files],
        "host_dependencies": manifest["host_dependencies"],
        "forbidden_capabilities": manifest["forbidden_capabilities"],
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Print a dry-run export plan for Product Skills.")
    parser.add_argument("--skill-id", default="", help="Product Skill id to export-plan.")
    parser.add_argument("--all", action="store_true", help="Plan every product Skill.")
    args = parser.parse_args(argv)

    if args.all:
        plan = [build_plan(skill_id) for skill_id in sorted(product_items())]
    elif args.skill_id:
        plan = build_plan(args.skill_id)
    else:
        fail("pass --all or --skill-id")
    print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
