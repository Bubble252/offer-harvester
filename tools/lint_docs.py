from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

REQUIRED_DOCS = [
    "10_open_source_readiness.md",
    "11_demo_walkthrough.md",
    "getting-started.md",
    "architecture.md",
    "reference/api.md",
    "reference/configuration.md",
    "operations/security.md",
    "operations/contributing.md",
    "operations/release.md",
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

PUBLIC_DOC_PAIRS = [
    ("docs/README.md", "docs/README.zh-CN.md"),
    ("docs/getting-started.md", "docs/getting-started.zh-CN.md"),
    ("docs/architecture.md", "docs/architecture.zh-CN.md"),
    ("docs/reference/api.md", "docs/reference/api.zh-CN.md"),
    (
        "docs/reference/configuration.md",
        "docs/reference/configuration.zh-CN.md",
    ),
    ("docs/operations/security.md", "docs/operations/security.zh-CN.md"),
    (
        "docs/operations/contributing.md",
        "docs/operations/contributing.zh-CN.md",
    ),
    ("docs/operations/release.md", "docs/operations/release.zh-CN.md"),
    ("docs/guides/skills.md", "docs/guides/skills.zh-CN.md"),
    (
        "docs/guides/skills/contact-email-coach.md",
        "docs/guides/skills/contact-email-coach.zh-CN.md",
    ),
    (
        "docs/guides/skills/advisor-due-diligence.md",
        "docs/guides/skills/advisor-due-diligence.zh-CN.md",
    ),
    (
        "docs/guides/skills/recommendation-letter-helper.md",
        "docs/guides/skills/recommendation-letter-helper.zh-CN.md",
    ),
    ("docs/guides/deepseek-harness.md", "docs/guides/deepseek-harness.zh-CN.md"),
    (
        "integrations/deepseek_harness/README.md",
        "integrations/deepseek_harness/README.zh-CN.md",
    ),
    ("skills/README.md", "skills/README.zh-CN.md"),
]

REQUIRED_PORTABLE_SKILL_IDS = {
    "evidence-claim-audit",
    "source-connector-authoring",
    "profile-field-normalization",
}

REQUIRED_PRODUCT_SKILL_IDS = {
    "contact-email-coach",
    "advisor-due-diligence",
    "recommendation-letter-helper",
}


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


def check_public_doc_pairs() -> None:
    for english, chinese in PUBLIC_DOC_PAIRS:
        if not (ROOT / english).exists():
            fail(f"missing public English document: {english}")
        if not (ROOT / chinese).exists():
            fail(f"missing public Chinese document: {chinese}")


def check_skill_catalog() -> None:
    path = ROOT / "skills" / "catalog.json"
    if not path.exists():
        fail("missing skills/catalog.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("skills", [])
    indexed = {item.get("skill_id"): item for item in entries}
    expected = REQUIRED_PORTABLE_SKILL_IDS | REQUIRED_PRODUCT_SKILL_IDS
    missing = sorted(expected - set(indexed))
    if missing:
        fail(f"skill catalog is missing required entries: {', '.join(missing)}")
    for skill_id in expected:
        item = indexed[skill_id]
        if item.get("no_send") is not True:
            fail(f"skill catalog entry must be no_send: {skill_id}")
        if not (ROOT / str(item.get("path", "")) / "SKILL.md").exists():
            fail(f"skill catalog entry has no SKILL.md: {skill_id}")


def main() -> None:
    check_required_docs()
    check_open_source_doc()
    check_portable_skill()
    check_public_doc_pairs()
    check_skill_catalog()
    print("doc lint passed")


if __name__ == "__main__":
    main()
