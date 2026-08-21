from __future__ import annotations

from typing import Any, Dict, List, Optional

from models import AgentRun, WorkflowEvent


class WorkflowEventRecorder:
    def __init__(self, run: AgentRun):
        self.run = run
        self.events: List[WorkflowEvent] = []

    def record(
        self,
        event_type: str,
        status: str = "completed",
        agent_name: str = "",
        payload: Optional[Dict[str, Any]] = None,
    ) -> WorkflowEvent:
        event = WorkflowEvent(
            run_id=self.run.run_id,
            target_id=self.run.target_id,
            workflow=self.run.workflow,
            event_type=event_type,  # type: ignore[arg-type]
            status=status,  # type: ignore[arg-type]
            agent_name=agent_name,
            payload=payload or {},
        )
        self.events.append(event)
        return event
