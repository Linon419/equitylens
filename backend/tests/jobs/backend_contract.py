import pytest

from app.jobs.errors import JobDispatchError


async def assert_backend_contract(backend, transport) -> None:
    first = await backend.enqueue(
        job_type="company_intelligence",
        payload={"job_id": "job-123"},
    )
    second = await backend.enqueue(
        job_type="company_intelligence",
        payload={"job_id": "job-123"},
    )

    assert first.job_id == second.job_id
    assert transport.payloads == [{"job_id": "job-123"}]

    transport.fail = True
    with pytest.raises(JobDispatchError) as error:
        await backend.enqueue(
            job_type="company_intelligence",
            payload={"job_id": "job-timeout"},
        )
    assert error.value.retryable is True
