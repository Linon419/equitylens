import json

import httpx
import pytest

from app.jobs.vercel_backend import VercelWorkflowBackend
from tests.jobs.backend_contract import assert_backend_contract


class WorkflowTransport:
    def __init__(self) -> None:
        self.payloads: list[dict] = []
        self.headers: list[httpx.Headers] = []
        self.urls: list[str] = []
        self.fail = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.fail:
            raise httpx.ReadTimeout("workflow timeout", request=request)
        payload = json.loads(request.content)
        self.payloads.append(payload)
        self.headers.append(request.headers)
        self.urls.append(str(request.url))
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
            supply_chain_trigger_url=(
                "https://web.example/api/internal/workflows/supply-chain-graph"
            ),
            filing_index_trigger_url=(
                "https://web.example/api/internal/workflows/filing-index"
            ),
        )
        await assert_backend_contract(backend, transport)

    headers = transport.headers[0]
    assert headers["authorization"] == f"Bearer {'i' * 32}"
    assert headers["x-idempotency-key"] == "company_intelligence-123"


@pytest.mark.asyncio
async def test_vercel_backend_routes_each_job_type_to_its_trigger() -> None:
    transport = WorkflowTransport()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(transport.handler)
    ) as client:
        backend = VercelWorkflowBackend(
            client,
            "https://web.example/api/internal/workflows/company-intelligence",
            "i" * 32,
            supply_chain_trigger_url=(
                "https://web.example/api/internal/workflows/supply-chain-graph"
            ),
            filing_index_trigger_url=(
                "https://web.example/api/internal/workflows/filing-index"
            ),
        )
        await backend.enqueue(
            job_type="company_intelligence",
            payload={"job_id": "company-123"},
        )
        await backend.enqueue(
            job_type="supply_chain_graph",
            payload={"job_id": "graph-123"},
        )
        await backend.enqueue(
            job_type="filing_index",
            payload={"job_id": "index-123"},
        )

    assert [header["x-idempotency-key"] for header in transport.headers] == [
        "company-123",
        "graph-123",
        "index-123",
    ]
    assert transport.urls == [
        "https://web.example/api/internal/workflows/company-intelligence",
        "https://web.example/api/internal/workflows/supply-chain-graph",
        "https://web.example/api/internal/workflows/filing-index",
    ]
