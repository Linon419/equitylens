import asyncio
from typing import Any

from app.jobs.errors import JobDispatchError
from app.jobs.schemas import JobSubmission

RQ_TASKS = {
    "company_intelligence": "app.jobs.tasks.run_company_intelligence",
    "supply_chain_graph": "app.jobs.tasks.run_supply_chain_graph",
    "filing_index": "app.jobs.tasks.run_filing_index",
}


class RQJobBackend:
    def __init__(self, queue: Any) -> None:
        self._queue = queue

    async def enqueue(
        self,
        *,
        job_type: str,
        payload: dict,
    ) -> JobSubmission:
        task_name = RQ_TASKS.get(job_type)
        if task_name is None or set(payload) != {"job_id"}:
            raise JobDispatchError("unsupported RQ job payload", retryable=False)
        provider_job_id = f"{job_type.replace('_', '-')}-{payload['job_id']}"
        try:
            existing = await asyncio.to_thread(
                self._queue.fetch_job,
                provider_job_id,
            )
            if existing is not None:
                status = await asyncio.to_thread(existing.get_status, refresh=True)
                status_value = getattr(status, "value", str(status))
                if status_value not in {"failed", "stopped", "canceled"}:
                    return JobSubmission(job_id=provider_job_id)
                await asyncio.to_thread(existing.delete)
            job = await asyncio.to_thread(
                self._queue.enqueue,
                task_name,
                kwargs={"job_id": str(payload["job_id"])},
                job_id=provider_job_id,
                job_timeout=600,
                result_ttl=86_400,
                failure_ttl=604_800,
            )
        except Exception as error:
            raise JobDispatchError("RQ dispatch failed", retryable=True) from error
        return JobSubmission(job_id=str(job.id))
