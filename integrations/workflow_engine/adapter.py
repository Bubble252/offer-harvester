from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class WorkflowEvent:
    """描述一次可审计的申请流程事件。"""

    event_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )


class WorkflowLogger:
    """记录流程事件，后续可替换为数据库或事件总线实现。"""

    def __init__(self) -> None:
        self.events: List[WorkflowEvent] = []

    def record(
        self, event_type: str, payload: Optional[Dict[str, Any]] = None
    ) -> WorkflowEvent:
        event = WorkflowEvent(event_type=event_type, payload=payload or {})
        self.events.append(event)
        return event
