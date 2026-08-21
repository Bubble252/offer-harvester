from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


class Workspace:
    def __init__(self, root: Optional[str] = None):
        env_root = os.environ.get("WORKSPACE_DIR")
        self.root = Path(root or env_root or "../../workspace").resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        for name in [
            "profiles",
            "user_documents",
            "advisor_sources",
            "advisors",
            "targets",
            "matches",
            "applications",
            "generated",
            "material_versions",
            "quality_reports",
            "agent_runs",
            "presentation_tasks",
            "reports",
        ]:
            (self.root / name).mkdir(exist_ok=True)

    def path(self, collection: str, item_id: str) -> Path:
        return self.root / collection / f"{item_id}.json"

    def write(self, collection: str, item: Dict[str, Any], id_field: str) -> Dict[str, Any]:
        item_id = item[id_field]
        self.path(collection, item_id).write_text(
            json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return item

    def read(self, collection: str, item_id: str) -> Optional[Dict[str, Any]]:
        path = self.path(collection, item_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list(self, collection: str) -> List[Dict[str, Any]]:
        items = []
        for path in sorted((self.root / collection).glob("*.json")):
            items.append(json.loads(path.read_text(encoding="utf-8")))
        return items

    def latest(self, collection: str) -> Optional[Dict[str, Any]]:
        items = self.list(collection)
        return items[-1] if items else None
