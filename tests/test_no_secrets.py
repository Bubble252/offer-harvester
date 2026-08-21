import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"OPENAI_API_KEY\s*=\s*sk-[A-Za-z0-9_-]+"),
    re.compile(r"API_KEY\s*=\s*sk-[A-Za-z0-9_-]+"),
]

IGNORED_PARTS = {
    ".git",
    ".venv",
    ".pytest_cache",
    "__pycache__",
    "workspace",
    "runs",
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
    ".txt",
    ".yml",
}


def iter_repo_text_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_PARTS for part in path.relative_to(ROOT).parts):
            continue
        if path.suffix in TEXT_SUFFIXES or path.name == ".gitignore":
            yield path


def test_no_api_secrets_committed():
    leaked = []
    for path in iter_repo_text_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            leaked.append(str(path.relative_to(ROOT)))

    assert leaked == []
