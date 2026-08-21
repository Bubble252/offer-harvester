from __future__ import annotations

from typing import List

from models import AdvisorProfile, AdvisorSource, AgentRun, WorkflowEvent, now_iso
from pydantic import BaseModel, Field
from services import parse_advisor_profile

from agents.base import compact_list
from agents.workflow_events import WorkflowEventRecorder


class AdvisorExtractionResult(BaseModel):
    advisor: AdvisorProfile
    agent_run: AgentRun
    events: List[WorkflowEvent] = Field(default_factory=list)


class AdvisorExtractionAgent:
    name = "AdvisorExtractionAgent"

    def extract(
        self,
        sources: List[AdvisorSource],
        advisor_id: str = "",
    ) -> AdvisorExtractionResult:
        run = AgentRun(
            target_id=advisor_id or (sources[-1].source_id if sources else "advisor_intake"),
            workflow="advisor_intake.extraction",
            status="running",
            input_summary={
                "advisor_id": advisor_id,
                "source_ids": [source.source_id for source in sources],
                "source_types": [source.source_type for source in sources],
                "trusted_source_count": len([source for source in sources if source.trusted]),
            },
        )
        recorder = WorkflowEventRecorder(run)
        recorder.record(
            "workflow_started",
            status="started",
            agent_name=self.name,
            payload={"source_count": len(sources), "advisor_id": advisor_id},
        )
        recorder.record("extraction_started", status="started", agent_name=self.name)

        advisor = parse_advisor_profile(sources)
        if advisor_id:
            advisor.advisor_id = advisor_id

        run.status = "completed"
        run.output_summary = {
            "advisor_id": advisor.advisor_id,
            "identity_confirmed": advisor.identity_confirmed,
            "research_directions": compact_list(advisor.research_directions),
            "source_ids": advisor.source_ids,
            "evidence_fields": [field for field, ids in advisor.evidence_map.items() if ids],
            "risk_count": len(advisor.risk_notes),
        }
        run.risk_tags = extraction_risk_tags(advisor, sources)
        run.ended_at = now_iso()
        recorder.record(
            "extraction_completed",
            agent_name=self.name,
            payload={
                "advisor_id": advisor.advisor_id,
                "identity_confirmed": advisor.identity_confirmed,
                "direction_count": len(advisor.research_directions),
                "risk_tags": run.risk_tags,
            },
        )
        return AdvisorExtractionResult(advisor=advisor, agent_run=run, events=recorder.events)


def extraction_risk_tags(advisor: AdvisorProfile, sources: List[AdvisorSource]) -> List[str]:
    tags = []
    if not sources:
        tags.append("missing_source")
    if sources and not any(source.trusted for source in sources):
        tags.append("untrusted_sources")
    if not advisor.identity_confirmed:
        tags.append("identity_review_required")
    if not advisor.research_directions:
        tags.append("direction_missing")
    if not advisor.source_ids:
        tags.append("evidence_missing")
    if any("LLM 增强解析未完成" in note for note in advisor.risk_notes):
        tags.append("llm_enrichment_incomplete")
    return list(dict.fromkeys(tags))
