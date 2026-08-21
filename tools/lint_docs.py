from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

REQUIRED_DOCS = [
    "10_open_source_readiness.md",
    "11_demo_walkthrough.md",
]

REQUIRED_CODE_PATH_MARKERS = [
    ("app/backend", "app/"),
    (".agents/skills", ".agents/"),
    ("integrations", "integrations/"),
    ("workspace.example", "workspace.example/"),
    ("tools", "tools/"),
]

REQUIRED_SKILL_FILES = [
    ".agents/skills/grad-apply-workflow/SKILL.md",
    ".agents/skills/grad-apply-workflow/workflows/material-drafter.md",
    ".agents/skills/grad-apply-workflow/workflows/material-reviewer.md",
    ".agents/skills/grad-apply-workflow/workflows/evidence-auditor.md",
    ".agents/skills/grad-apply-workflow/references/data-locations.md",
    ".agents/skills/grad-apply-workflow/references/evidence-rules.md",
    ".agents/skills/grad-apply-workflow/references/safety-rules.md",
]


def fail(message: str) -> None:
    print(f"doc lint failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def read_doc(name: str) -> str:
    path = DOCS / name
    if not path.exists():
        fail(f"missing docs/{name}")
    return path.read_text(encoding="utf-8")


def check_required_docs() -> None:
    for name in REQUIRED_DOCS:
        read_doc(name)


def check_open_source_doc() -> None:
    text = read_doc("10_open_source_readiness.md")
    for canonical, doc_marker in REQUIRED_CODE_PATH_MARKERS:
        if canonical not in text and doc_marker not in text:
            fail(f"docs/10_open_source_readiness.md missing path marker: {canonical}")


def check_portable_skill() -> None:
    for relative_path in REQUIRED_SKILL_FILES:
        if not (ROOT / relative_path).exists():
            fail(f"missing portable skill file: {relative_path}")


def main() -> None:
    check_required_docs()
    check_open_source_doc()
    check_portable_skill()
    print("doc lint passed")


if __name__ == "__main__":
    main()
