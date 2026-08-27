from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_PREFIXES = (
    "README",
    "CHANGELOG",
    "CONTRIBUTING",
    "SECURITY",
    "CODE_OF_CONDUCT",
    "docs/README",
    "docs/guides/",
    "docs/reference/",
    "docs/operations/",
    "integrations/deepseek_harness/README",
    ".github/",
)
FORBIDDEN_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)(?:postgres(?:ql)?|mysql)://[^`\s]+"),
    re.compile(r"(?<!\w)/(?:home|Users|root)/[A-Za-z0-9_.-]+/"),
]
TEXT_SUFFIXES = {
    ".cfg",
    ".css",
    ".env",
    ".html",
    ".js",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yml",
}


def public_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return [
        ROOT / relative
        for relative in result.stdout.splitlines()
        if relative.startswith(PUBLIC_PREFIXES) and Path(relative).suffix in TEXT_SUFFIXES
    ]


def main() -> None:
    leaked: list[str] = []
    for path in public_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in FORBIDDEN_PATTERNS):
            leaked.append(str(path.relative_to(ROOT)))
    if leaked:
        print("public boundary check failed:", file=sys.stderr)
        for path in leaked:
            print(f"- {path}", file=sys.stderr)
        raise SystemExit(1)
    print("public boundary check passed")


if __name__ == "__main__":
    main()
