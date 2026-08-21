from __future__ import annotations

from typing import Any, Dict


def make_check(name: str, passed: bool, message: str, **extra: Any) -> Dict[str, Any]:
    check: Dict[str, Any] = {"name": name, "passed": passed, "message": message}
    check.update(extra)
    return check
