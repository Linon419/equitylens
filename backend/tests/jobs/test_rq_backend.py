import re
from dataclasses import dataclass

import pytest

from app.jobs.rq_backend import RQJobBackend
from tests.jobs.backend_contract import assert_backend_contract


@dataclass
class FakeRQJob:
    id: str
    status: str = "queued"
    deleted: bool = False

    def get_status(self, *, refresh: bool = True) -> str:
        return self.status

    def delete(self) -> None:
        self.deleted = True


class FakeQueue:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.payloads: list[dict] = []
        self.jobs: dict[str, FakeRQJob] = {}
        self.fail = False

    def fetch_job(self, job_id: str):
        job = self.jobs.get(job_id)
        return None if job is not None and job.deleted else job

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
    assert job_id == "company-intelligence-job-123"
    assert re.fullmatch(r"[A-Za-z0-9_-]+", job_id)
    assert options["job_timeout"] == 600
    assert options["result_ttl"] == 86400
    assert options["failure_ttl"] == 604800
    assert submission.job_id == "company-intelligence-job-123"


@pytest.mark.asyncio
async def test_rq_backend_routes_supply_chain_graph_task() -> None:
    queue = FakeQueue()
    backend = RQJobBackend(queue)

    submission = await backend.enqueue(
        job_type="supply_chain_graph",
        payload={"job_id": "graph-123"},
    )

    function, payload, job_id, _ = queue.calls[0]
    assert function == "app.jobs.tasks.run_supply_chain_graph"
    assert payload == {"job_id": "graph-123"}
    assert job_id == "supply-chain-graph-graph-123"
    assert submission.job_id == job_id


@pytest.mark.asyncio
async def test_rq_backend_routes_filing_index_task() -> None:
    queue = FakeQueue()
    backend = RQJobBackend(queue)

    submission = await backend.enqueue(
        job_type="filing_index",
        payload={"job_id": "index-123"},
    )

    function, payload, job_id, _ = queue.calls[0]
    assert function == "app.jobs.tasks.run_filing_index"
    assert payload == {"job_id": "index-123"}
    assert job_id == "filing-index-index-123"
    assert submission.job_id == job_id


@pytest.mark.asyncio
async def test_rq_backend_satisfies_shared_contract() -> None:
    queue = FakeQueue()
    await assert_backend_contract(RQJobBackend(queue), queue)


@pytest.mark.asyncio
async def test_rq_backend_requeues_a_terminally_failed_job() -> None:
    queue = FakeQueue()
    backend = RQJobBackend(queue)
    first = await backend.enqueue(
        job_type="supply_chain_graph",
        payload={"job_id": "graph-retry"},
    )
    queue.jobs[first.job_id].status = "failed"

    retried = await backend.enqueue(
        job_type="supply_chain_graph",
        payload={"job_id": "graph-retry"},
    )

    assert retried.job_id == first.job_id
    assert len(queue.calls) == 2
