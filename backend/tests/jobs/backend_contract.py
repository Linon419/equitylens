import pytest

from app.jobs.errors import JobDispatchError


async def assert_backend_contract(backend, transport) -> None:
    for job_type in (
        "company_intelligence",
        "supply_chain_graph",
        "filing_index",
    ):
        first = await backend.enqueue(
            job_type=job_type,
            payload={"job_id": f"{job_type}-123"},
        )
        second = await backend.enqueue(
            job_type=job_type,
            payload={"job_id": f"{job_type}-123"},
        )
        assert first.job_id == second.job_id

    assert transport.payloads == [
        {"job_id": "company_intelligence-123"},
        {"job_id": "supply_chain_graph-123"},
        {"job_id": "filing_index-123"},
    ]

    transport.fail = True
    with pytest.raises(JobDispatchError) as error:
        await backend.enqueue(
            job_type="company_intelligence",
            payload={"job_id": "job-timeout"},
        )
    assert error.value.retryable is True

    with pytest.raises(JobDispatchError) as unsupported:
        await backend.enqueue(job_type="unknown", payload={"job_id": "job-123"})
    assert unsupported.value.retryable is False

    with pytest.raises(JobDispatchError) as malformed:
        await backend.enqueue(
            job_type="supply_chain_graph",
            payload={"job_id": "job-123", "extra": True},
        )
    assert malformed.value.retryable is False
