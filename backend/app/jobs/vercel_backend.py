import httpx

from app.jobs.errors import JobDispatchError
from app.jobs.schemas import JobSubmission


class VercelWorkflowBackend:
    def __init__(
        self,
        client: httpx.AsyncClient,
        trigger_url: str,
        internal_secret: str,
    ) -> None:
        self._client = client
        self._trigger_url = trigger_url
        self._internal_secret = internal_secret
        self._submissions: dict[str, JobSubmission] = {}

    async def enqueue(
        self,
        *,
        job_type: str,
        payload: dict,
    ) -> JobSubmission:
        if job_type != "company_intelligence" or set(payload) != {"job_id"}:
            raise JobDispatchError(
                "unsupported Workflow payload",
                retryable=False,
            )
        job_id = str(payload["job_id"])
        existing = self._submissions.get(job_id)
        if existing is not None:
            return existing
        try:
            response = await self._client.post(
                self._trigger_url,
                json={"job_id": job_id},
                headers={
                    "Authorization": f"Bearer {self._internal_secret}",
                    "x-idempotency-key": job_id,
                },
            )
        except httpx.HTTPError as error:
            raise JobDispatchError(
                "Workflow dispatch failed",
                retryable=True,
            ) from error
        if response.status_code >= 500:
            raise JobDispatchError("Workflow dispatch failed", retryable=True)
        if response.status_code != 202:
            raise JobDispatchError("Workflow dispatch rejected", retryable=False)
        try:
            run_id = str(response.json()["run_id"])
        except (KeyError, TypeError, ValueError) as error:
            raise JobDispatchError(
                "Workflow response is invalid",
                retryable=False,
            ) from error
        submission = JobSubmission(job_id=run_id)
        self._submissions[job_id] = submission
        return submission
