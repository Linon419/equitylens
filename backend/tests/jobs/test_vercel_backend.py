import json

import httpx
import pytest

from app.jobs.vercel_backend import VercelWorkflowBackend
from tests.jobs.backend_contract import assert_backend_contract


class WorkflowTransport:
    def __init__(self) -> None:
        self.payloads: list[dict] = []
        self.headers: list[httpx.Headers] = []
        self.fail = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.fail:
            raise httpx.ReadTimeout("workflow timeout", request=request)
        payload = json.loads(request.content)
        self.payloads.append(payload)
        self.headers.append(request.headers)
        return httpx.Response(
            202,
            json={"run_id": f"run:{payload['job_id']}"},
            request=request,
        )


@pytest.mark.asyncio
async def test_vercel_backend_satisfies_shared_contract() -> None:
    transport = WorkflowTransport()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(transport.handler)
    ) as client:
        backend = VercelWorkflowBackend(
            client,
            "https://web.example/api/internal/workflows/company-intelligence",
            "i" * 32,
        )
        await assert_backend_contract(backend, transport)

    headers = transport.headers[0]
    assert headers["authorization"] == f"Bearer {'i' * 32}"
    assert headers["x-idempotency-key"] == "job-123"
