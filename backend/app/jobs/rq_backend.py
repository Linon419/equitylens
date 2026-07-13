import asyncio
from typing import Any

from app.jobs.errors import JobDispatchError
from app.jobs.schemas import JobSubmission

TASK_NAME = "app.jobs.tasks.run_company_intelligence"


class RQJobBackend:
    def __init__(self, queue: Any) -> None:
        self._queue = queue

    async def enqueue(
        self,
        *,
        job_type: str,
        payload: dict,
    ) -> JobSubmission:
        if job_type != "company_intelligence" or set(payload) != {"job_id"}:
            raise JobDispatchError("unsupported RQ job payload", retryable=False)
        provider_job_id = f"company-intelligence:{payload['job_id']}"
        try:
            existing = await asyncio.to_thread(
                self._queue.fetch_job,
                provider_job_id,
            )
            if existing is not None:
                return JobSubmission(job_id=provider_job_id)
            job = await asyncio.to_thread(
                self._queue.enqueue,
                TASK_NAME,
                kwargs={"job_id": str(payload["job_id"])},
                job_id=provider_job_id,
                job_timeout=600,
                result_ttl=86_400,
                failure_ttl=604_800,
            )
        except Exception as error:
            raise JobDispatchError("RQ dispatch failed", retryable=True) from error
        return JobSubmission(job_id=str(job.id))
