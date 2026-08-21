from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

IGNORED_PARTS = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "workspace",
    "workspace.demo",
}

TEXT_SUFFIXES = {
    ".cfg",
    ".css",
    ".env",
    ".example",
    ".html",
    ".js",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yml",
}

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"OPENAI_API_KEY\s*=\s*sk-[A-Za-z0-9_-]+"),
    re.compile(r"API_KEY\s*=\s*sk-[A-Za-z0-9_-]+"),
]

REQUIRED_GITIGNORE_RULES = {
    ".env",
    ".env.*",
    "workspace/",
    "workspace.demo/",
    "*.key",
    "*.pem",
    "*.p12",
    "*.pfx",
    "*.pdf",
    "*.docx",
    "*.xlsx",
    "*.pptx",
    "*.sqlite3",
    "*.zip",
    ".venv/",
    ".ruff_cache/",
}

FORBIDDEN_TRACKED_PREFIXES = (
    "workspace/",
    "workspace.demo/",
    "runs/",
    "app/backend/data/",
)

FORBIDDEN_TRACKED_NAMES = {
    ".env",
}

SENSITIVE_SUFFIXES = {
    ".key",
    ".pem",
    ".p12",
    ".pfx",
}

EXTERNAL_PROJECT_PATH_MARKERS = {
    "ai-job-search-master",
    "PPTAgent",
    "居丽叶简历项目2",
}


def fail(message: str) -> None:
    print(f"security guard failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def git_tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def iter_repo_text_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in IGNORED_PARTS for part in relative.parts):
            continue
        if path.suffix in TEXT_SUFFIXES or path.name in {".gitignore", "NOTICE"}:
            yield path


def check_gitignore() -> None:
    gitignore = ROOT / ".gitignore"
    if not gitignore.exists():
        fail(".gitignore is missing")
    rules = {
        line.strip()
        for line in gitignore.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    missing = sorted(REQUIRED_GITIGNORE_RULES - rules)
    if missing:
        fail(f".gitignore is missing required rules: {', '.join(missing)}")


def check_tracked_files() -> None:
    tracked = git_tracked_files()
    for path in tracked:
        relative = Path(path)
        if path in FORBIDDEN_TRACKED_NAMES:
            fail(f"forbidden tracked file: {path}")
        if path.startswith(FORBIDDEN_TRACKED_PREFIXES):
            fail(f"forbidden tracked local data path: {path}")
        if relative.suffix in SENSITIVE_SUFFIXES:
            fail(f"forbidden tracked sensitive file suffix: {path}")
        if any(marker in relative.parts for marker in EXTERNAL_PROJECT_PATH_MARKERS):
            fail(f"external reference project appears to be tracked: {path}")
        full_path = ROOT / relative
        if full_path.exists() and full_path.is_file() and full_path.stat().st_size > 5_000_000:
            fail(f"large tracked file needs review before open-source use: {path}")


def check_notice() -> None:
    notice = ROOT / "NOTICE"
    if not notice.exists():
        fail("NOTICE is missing")
    text = notice.read_text(encoding="utf-8", errors="ignore")
    for marker in ["ai-job-search-master", "PPTAgent"]:
        if marker not in text:
            fail(f"NOTICE does not mention reference boundary for {marker}")


def check_secrets() -> None:
    leaked = []
    for path in iter_repo_text_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            leaked.append(str(path.relative_to(ROOT)))
    if leaked:
        fail(f"possible API secret committed in: {', '.join(sorted(leaked))}")


def main() -> None:
    check_gitignore()
    check_tracked_files()
    check_notice()
    check_secrets()
    print("security guards passed")


if __name__ == "__main__":
    main()
