from __future__ import annotations

import asyncio
import inspect
import time
from typing import Any, Callable, Dict, Iterable, List, Optional

from pydantic import BaseModel, Field


class SwarmTask(BaseModel):
    task_id: str
    role: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[str] = Field(default_factory=list)


class SwarmWorkerResult(BaseModel):
    task_id: str
    role: str
    status: str = "completed"
    output: Dict[str, Any] = Field(default_factory=dict)
    model_name: str = "rule-local"
    elapsed_ms: int = 0
    error: str = ""


class SwarmDecision(BaseModel):
    use_swarm: bool
    reason: str
    task_count: int
    independent_task_count: int = 0


class SharedContext(BaseModel):
    run_id: str
    contributions: List[SwarmWorkerResult] = Field(default_factory=list)
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    failures: List[Dict[str, Any]] = Field(default_factory=list)
    events: List[Dict[str, Any]] = Field(default_factory=list)

    def add_result(self, result: SwarmWorkerResult) -> None:
        self.contributions.append(result)
        self.events.append(
            {
                "event_type": "worker_completed"
                if result.status == "completed"
                else "worker_failed",
                "task_id": result.task_id,
                "role": result.role,
                "status": result.status,
            }
        )
        if result.status != "completed":
            self.failures.append(
                {"task_id": result.task_id, "role": result.role, "error": result.error}
            )


class SwarmRouter:
    def decide(self, tasks: Iterable[SwarmTask]) -> SwarmDecision:
        task_list = list(tasks)
        independent = [task for task in task_list if not task.depends_on]
        if len(task_list) < 2:
            return SwarmDecision(
                use_swarm=False,
                reason="任务数量不足，直接单 Agent 执行。",
                task_count=len(task_list),
                independent_task_count=len(independent),
            )
        if not independent:
            return SwarmDecision(
                use_swarm=False,
                reason="任务存在串行依赖，保留顺序执行。",
                task_count=len(task_list),
                independent_task_count=0,
            )
        return SwarmDecision(
            use_swarm=True,
            reason="存在两个以上可独立执行的子任务，允许受控并行。",
            task_count=len(task_list),
            independent_task_count=len(independent),
        )


WorkerCallable = Callable[[SwarmTask, SharedContext], Any]


class LeadAgent:
    """Coordinator protocol implementation; it never writes business facts."""

    def __init__(self, *, timeout_seconds: float = 20.0):
        self.timeout_seconds = timeout_seconds
        self.router = SwarmRouter()

    async def run(
        self,
        run_id: str,
        tasks: List[SwarmTask],
        worker: WorkerCallable,
        *,
        synthesizer: Optional[Callable[[SharedContext], Any]] = None,
    ) -> tuple[SwarmDecision, SharedContext, Any]:
        decision = self.router.decide(tasks)
        context = SharedContext(run_id=run_id)
        context.events.append(
            {
                "event_type": "swarm_started",
                "task_count": len(tasks),
                "use_swarm": decision.use_swarm,
            }
        )
        if decision.use_swarm:
            results = []
            completed_ids = set()
            remaining = list(tasks)
            while remaining:
                ready = [task for task in remaining if set(task.depends_on) <= completed_ids]
                if not ready:
                    ready = remaining[:1]
                batch = await asyncio.gather(
                    *(self._run_worker(task, context, worker) for task in ready),
                    return_exceptions=False,
                )
                results.extend(batch)
                completed_ids.update(task.task_id for task in ready)
                remaining = [task for task in remaining if task.task_id not in completed_ids]
        else:
            results = []
            for task in tasks:
                results.append(await self._run_worker(task, context, worker))
        for result in results:
            context.add_result(result)
        if synthesizer is None:
            synthesis = SynthesisAgent().synthesize(context)
        else:
            synthesis = synthesizer(context)
            if inspect.isawaitable(synthesis):
                synthesis = await synthesis
        context.events.append(
            {"event_type": "swarm_completed", "failure_count": len(context.failures)}
        )
        return decision, context, synthesis

    async def _run_worker(
        self,
        task: SwarmTask,
        context: SharedContext,
        worker: WorkerCallable,
    ) -> SwarmWorkerResult:
        started = time.perf_counter()
        try:
            output = worker(task, context)
            if inspect.isawaitable(output):
                output = await asyncio.wait_for(output, timeout=self.timeout_seconds)
            return SwarmWorkerResult(
                task_id=task.task_id,
                role=task.role,
                output=output if isinstance(output, dict) else {"value": output},
                elapsed_ms=round((time.perf_counter() - started) * 1000),
            )
        except Exception as exc:
            return SwarmWorkerResult(
                task_id=task.task_id,
                role=task.role,
                status="failed",
                error=str(exc),
                elapsed_ms=round((time.perf_counter() - started) * 1000),
            )


class SynthesisAgent:
    def synthesize(self, context: SharedContext) -> Dict[str, Any]:
        outputs = [
            result.output for result in context.contributions if result.status == "completed"
        ]
        return {
            "status": "needs_review" if context.failures or context.conflicts else "completed",
            "contribution_count": len(outputs),
            "outputs": outputs,
            "conflicts": list(context.conflicts),
            "failures": list(context.failures),
            "requires_evidence_audit": True,
        }
