import json
from typing import Any

import httpx
import pytest

from app.chat.tavily_discovery import TavilyWebSearchProvider


class FakeRunnable:
    def __init__(self, output: dict[str, Any]) -> None:
        self.output = output
        self.calls: list[Any] = []

    async def ainvoke(self, messages: Any) -> dict[str, Any]:
        self.calls.append(messages)
        return self.output


class FakePlanner:
    def __init__(self, output: dict[str, Any]) -> None:
        self.runnable = FakeRunnable(output)
        self.calls: list[tuple[type[Any], dict[str, Any]]] = []

    def with_structured_output(
        self,
        schema: type[Any],
        **options: Any,
    ) -> FakeRunnable:
        self.calls.append((schema, options))
        return self.runnable


@pytest.mark.asyncio
async def test_deepseek_plans_queries_and_tavily_returns_candidates() -> None:
    planner = FakePlanner(
        {
            "should_search": True,
            "reason": "Current external evidence is material.",
            "queries": [
                "SNDK latest investor relations NAND demand",
                "SNDK SEC filing supply chain customers",
            ],
        }
    )
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        query = request.read().decode()
        suffix = "ir" if "investor relations" in query else "sec"
        return httpx.Response(
            200,
            json={
                "request_id": f"tavily-{suffix}",
                "results": [
                    {
                        "title": f"SNDK {suffix}",
                        "url": f"https://investor.sandisk.com/{suffix}",
                        "content": "Search snippet",
                        "score": 0.91,
                    }
                ],
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = TavilyWebSearchProvider(
            planner,
            client,
            api_key="tvly-test",
            model_id="deepseek-research",
            max_queries=3,
            max_results=5,
            search_depth="basic",
            structured_output_method="json_mode",
        )
        discovery = await provider.search(
            question="What is SNDK's latest demand outlook?",
            company_name="SanDisk Corporation",
            symbol="SNDK",
            internal_coverage="partial",
            locale="en-US",
            official_hosts=("investor.sandisk.com",),
        )

    assert planner.calls[0][1] == {"method": "json_mode"}
    assert len(requests) == 2
    assert requests[0].headers["Authorization"] == "Bearer tvly-test"
    assert requests[0].url == "https://api.tavily.com/search"
    assert json.loads(requests[0].read()) == {
        "query": "SNDK latest investor relations NAND demand",
        "search_depth": "basic",
        "max_results": 5,
        "topic": "finance",
        "include_answer": False,
        "include_raw_content": False,
        "include_images": False,
        "include_domains": [
            "sec.gov",
            "nasdaq.com",
            "nyse.com",
            "cboe.com",
            "reuters.com",
            "ft.com",
            "wsj.com",
            "bloomberg.com",
            "finance.yahoo.com",
            "investor.sandisk.com",
        ],
    }
    assert discovery.provider_request_id == "tavily-ir,tavily-sec"
    assert [call.queries for call in discovery.calls] == [
        ["SNDK latest investor relations NAND demand"],
        ["SNDK SEC filing supply chain customers"],
    ]
    assert [call.ordinal for call in discovery.calls] == [0, 1]
    assert discovery.calls[0].candidates[0].url == (
        "https://investor.sandisk.com/ir"
    )
    assert discovery.calls[0].candidates[0].title == "SNDK ir"


@pytest.mark.asyncio
async def test_deepseek_can_skip_tavily_search() -> None:
    planner = FakePlanner(
        {
            "should_search": False,
            "reason": "Internal filing evidence is complete.",
            "queries": [],
        }
    )

    def unexpected_request(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected Tavily request: {request.url}")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(unexpected_request)
    ) as client:
        discovery = await TavilyWebSearchProvider(
            planner,
            client,
            api_key="tvly-test",
            model_id="deepseek-research",
            structured_output_method="json_mode",
        ).search(
            question="Explain the 2025 revenue disclosed in the 10-K.",
            company_name="SanDisk Corporation",
            symbol="SNDK",
            internal_coverage="complete",
            locale="en-US",
        )

    assert discovery.calls == []
    assert discovery.provider_request_id is None


@pytest.mark.asyncio
async def test_tavily_supports_free_keyless_search() -> None:
    planner = FakePlanner(
        {
            "should_search": True,
            "reason": "Current external evidence is material.",
            "queries": ["SNDK latest news"],
        }
    )
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"request_id": "keyless-1", "results": []},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        discovery = await TavilyWebSearchProvider(
            planner,
            client,
            api_key=None,
            model_id="deepseek-research",
            structured_output_method="json_mode",
        ).search(
            question="What happened to SNDK today?",
            company_name="SanDisk Corporation",
            symbol="SNDK",
            internal_coverage="complete",
            locale="en-US",
        )

    assert requests[0].headers["X-Tavily-Access-Mode"] == "keyless"
    assert "Authorization" not in requests[0].headers
    assert discovery.provider_request_id == "keyless-1"


@pytest.mark.asyncio
async def test_tavily_rejects_an_invalid_agent_search_plan() -> None:
    planner = FakePlanner(
        {
            "should_search": True,
            "reason": "Search requested without a query.",
            "queries": [],
        }
    )

    transport = httpx.MockTransport(lambda _: None)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = TavilyWebSearchProvider(
            planner,
            client,
            api_key="tvly-test",
            model_id="deepseek-research",
            structured_output_method="json_mode",
        )
        with pytest.raises(ValueError, match="at least one query"):
            await provider.search(
                question="What happened today?",
                company_name="SanDisk Corporation",
                symbol="SNDK",
                internal_coverage="complete",
                locale="en-US",
            )
