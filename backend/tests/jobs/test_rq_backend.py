from dataclasses import dataclass

import pytest

from app.jobs.rq_backend import RQJobBackend
from tests.jobs.backend_contract import assert_backend_contract


@dataclass
class FakeRQJob:
    id: str


class FakeQueue:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.payloads: list[dict] = []
        self.jobs: dict[str, FakeRQJob] = {}
        self.fail = False

    def fetch_job(self, job_id: str):
        return self.jobs.get(job_id)

    def enqueue(self, function: str, **options):
        if self.fail:
            raise TimeoutError("Redis timeout")
        job_id = options["job_id"]
        payload = options["kwargs"]
        self.calls.append((function, payload, job_id, options))
        self.payloads.append(payload)
        job = FakeRQJob(job_id)
        self.jobs[job_id] = job
        return job


@pytest.mark.asyncio
async def test_rq_backend_enqueues_stable_task_and_job_id() -> None:
    queue = FakeQueue()
    backend = RQJobBackend(queue)

    submission = await backend.enqueue(
        job_type="company_intelligence",
        payload={"job_id": "job-123"},
    )

    function, payload, job_id, options = queue.calls[0]
    assert function == "app.jobs.tasks.run_company_intelligence"
    assert payload == {"job_id": "job-123"}
    assert job_id == "company-intelligence:job-123"
    assert options["job_timeout"] == 600
    assert options["result_ttl"] == 86400
    assert options["failure_ttl"] == 604800
    assert submission.job_id == "company-intelligence:job-123"


@pytest.mark.asyncio
async def test_rq_backend_satisfies_shared_contract() -> None:
    queue = FakeQueue()
    await assert_backend_contract(RQJobBackend(queue), queue)
