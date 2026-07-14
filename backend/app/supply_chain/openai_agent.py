import asyncio
import json
import time
from collections.abc import Callable
from typing import Any, Literal

import httpx
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.supply_chain.contracts import OfficialSourceTools
from app.supply_chain.prompts import (
    company_payload,
    extraction_system_prompt,
    localization_system_prompt,
    source_planning_system_prompt,
    verification_system_prompt,
)
from app.supply_chain.schemas import (
    AcceptedGraph,
    CompanyIdentity,
    GraphDraft,
    GraphLocalization,
    GraphVerification,
    OfficialSourceDocument,
    OfficialSourceMetadata,
    SourcePlan,
    SourceType,
)

type OutputValidator[ResultT: BaseModel] = Callable[[ResultT], None]
TRUNCATION_MARKER = "\n[TRUNCATED]"


class SupplyChainAgentError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool = False) -> None:
        self.code = code
        self.retryable = retryable
        super().__init__(code)

    @classmethod
    def from_provider(cls, error: Exception) -> "SupplyChainAgentError":
        status_code = getattr(error, "status_code", None)
        retryable_names = {
            "APIConnectionError",
            "APITimeoutError",
            "InternalServerError",
            "RateLimitError",
        }
        retryable = (
            isinstance(
                error, (TimeoutError, httpx.TimeoutException, httpx.TransportError)
            )
            or error.__class__.__name__ in retryable_names
            or isinstance(status_code, int)
            and (status_code == 429 or status_code >= 500)
        )
        return cls(
            "AGENT_PROVIDER_UNAVAILABLE" if retryable else "AGENT_PROVIDER_REJECTED",
            retryable=retryable,
        )


class ListOfficialSources(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=240)
    source_types: tuple[SourceType, ...] = Field(min_length=1, max_length=4)

    @field_validator("source_types")
    @classmethod
    def validate_unique_types(
        cls,
        value: tuple[SourceType, ...],
    ) -> tuple[SourceType, ...]:
        if len(value) != len(set(value)):
            raise ValueError("duplicate source types")
        return value


class FetchOfficialSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1, max_length=255)


class OpenAISupplyChainAgent:
    def __init__(
        self,
        *,
        model: Any,
        model_id: str | None = None,
        schema_version: str = "supply-chain-graph.v1",
        prompt_version: str = "supply-chain-graph.2026-07-14",
        stage_timeout_seconds: float = 60,
        max_source_chars: int = 300_000,
        max_tool_result_chars: int = 40_000,
        max_tool_calls: int = 8,
    ) -> None:
        if stage_timeout_seconds <= 0:
            raise ValueError("stage_timeout_seconds must be positive")
        if max_source_chars < 64 or max_tool_result_chars < 64:
            raise ValueError("source character limits are too small")
        if not 1 <= max_tool_calls <= 8:
            raise ValueError("max_tool_calls must be between one and eight")
        self._model = model
        self.model_id = model_id or getattr(model, "model_name", "unknown")
        self.schema_version = schema_version
        self.prompt_version = prompt_version
        self._stage_timeout_seconds = stage_timeout_seconds
        self._max_source_chars = max_source_chars
        self._max_tool_result_chars = max_tool_result_chars
        self._max_tool_calls = max_tool_calls

    async def plan_sources(
        self,
        *,
        company: CompanyIdentity,
        tools: OfficialSourceTools,
    ) -> SourcePlan:
        system_prompt = source_planning_system_prompt(
            schema_version=self.schema_version,
            prompt_version=self.prompt_version,
        )
        messages: list[BaseMessage] = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=_json(company_payload(company))),
        ]
        bound = self._model.bind_tools(
            [ListOfficialSources, FetchOfficialSource],
            strict=True,
            parallel_tool_calls=False,
        )
        catalog: dict[str, OfficialSourceMetadata] = {}
        fetched_ids: set[str] = set()
        tool_call_count = 0
        while True:
            response = await self._invoke_tool_model(bound, messages)
            messages.append(response)
            calls = response.tool_calls
            if not calls:
                break
            if tool_call_count + len(calls) > self._max_tool_calls:
                raise SupplyChainAgentError("SOURCE_TOOL_LIMIT_REACHED")
            for call in calls:
                result = await self._execute_tool(
                    call,
                    company=company,
                    tools=tools,
                    catalog=catalog,
                    fetched_ids=fetched_ids,
                )
                tool_call_count += 1
                messages.append(
                    ToolMessage(
                        content=_json(result),
                        tool_call_id=str(call.get("id", "")),
                    )
                )
        if not fetched_ids:
            raise SupplyChainAgentError("SOURCE_PLAN_EMPTY")
        plan = await self._invoke_structured(
            schema=SourcePlan,
            stage="plan_sources",
            messages=messages,
            validator=lambda result: _validate_source_plan(result, fetched_ids),
            tool_count=tool_call_count,
        )
        return plan

    async def extract_graph(
        self,
        *,
        company: CompanyIdentity,
        sources: list[OfficialSourceDocument],
    ) -> GraphDraft:
        source_payload = self._bounded_sources(sources)
        messages = self._stage_messages(
            extraction_system_prompt,
            {
                "company": company_payload(company),
                "sources": source_payload,
            },
        )
        source_keys = {source.source_key for source in sources}
        return await self._invoke_structured(
            schema=GraphDraft,
            stage="extract_graph",
            messages=messages,
            validator=lambda result: _validate_draft(result, source_keys),
        )

    async def verify_graph(
        self,
        *,
        draft: GraphDraft,
        sources: list[OfficialSourceDocument],
    ) -> GraphVerification:
        messages = self._stage_messages(
            verification_system_prompt,
            {
                "draft": draft.model_dump(mode="json"),
                "sources": self._bounded_sources(sources),
            },
        )
        edge_keys = {edge.edge_key for edge in draft.edges}
        source_keys = {source.source_key for source in sources}
        return await self._invoke_structured(
            schema=GraphVerification,
            stage="verify_graph",
            messages=messages,
            validator=lambda result: _validate_verification(
                result,
                edge_keys=edge_keys,
                source_keys=source_keys,
            ),
        )

    async def localize_graph(
        self,
        *,
        graph: AcceptedGraph,
        locale: Literal["zh"] = "zh",
    ) -> GraphLocalization:
        if locale != "zh":
            raise SupplyChainAgentError("AGENT_LOCALE_UNSUPPORTED")
        messages = self._stage_messages(
            localization_system_prompt,
            {"graph": graph.model_dump(mode="json"), "locale": locale},
        )
        return await self._invoke_structured(
            schema=GraphLocalization,
            stage="localize_graph",
            messages=messages,
        )

    def _stage_messages(
        self,
        prompt_builder: Callable[..., str],
        payload: dict[str, object],
    ) -> list[BaseMessage]:
        return [
            SystemMessage(
                content=prompt_builder(
                    schema_version=self.schema_version,
                    prompt_version=self.prompt_version,
                )
            ),
            HumanMessage(content=_json(payload)),
        ]

    async def _invoke_tool_model(
        self,
        runnable: Any,
        messages: list[BaseMessage],
    ) -> AIMessage:
        try:
            async with asyncio.timeout(self._stage_timeout_seconds):
                result = await runnable.ainvoke(messages)
        except SupplyChainAgentError:
            raise
        except Exception as error:
            raise SupplyChainAgentError.from_provider(error) from None
        if not isinstance(result, AIMessage):
            raise SupplyChainAgentError("SOURCE_TOOL_RESPONSE_INVALID")
        return result

    async def _execute_tool(
        self,
        call: dict[str, Any],
        *,
        company: CompanyIdentity,
        tools: OfficialSourceTools,
        catalog: dict[str, OfficialSourceMetadata],
        fetched_ids: set[str],
    ) -> dict[str, object]:
        name = call.get("name")
        args = call.get("args")
        if name not in {"ListOfficialSources", "FetchOfficialSource"}:
            raise SupplyChainAgentError("SOURCE_TOOL_UNKNOWN")
        if not isinstance(args, dict):
            raise SupplyChainAgentError("SOURCE_TOOL_ARGUMENTS_INVALID")
        try:
            request = (
                ListOfficialSources.model_validate(args)
                if name == "ListOfficialSources"
                else FetchOfficialSource.model_validate(args)
            )
        except ValidationError:
            raise SupplyChainAgentError("SOURCE_TOOL_ARGUMENTS_INVALID") from None
        try:
            if name == "ListOfficialSources":
                assert isinstance(request, ListOfficialSources)
                sources = await tools.list_official_sources(
                    company=company,
                    query=request.query,
                    source_types=request.source_types,
                )
                catalog.update({source.source_id: source for source in sources})
                return {
                    "sources": [source.model_dump(mode="json") for source in sources]
                }
            assert isinstance(request, FetchOfficialSource)
            if request.source_id not in catalog:
                raise SupplyChainAgentError("SOURCE_NOT_IN_CATALOG")
            document = await tools.fetch_official_source(source_id=request.source_id)
            if document.source_id != request.source_id:
                raise SupplyChainAgentError("SOURCE_TOOL_RESULT_INVALID")
            fetched_ids.add(document.source_id)
            payload = document.model_dump(mode="json")
            payload["body_text"] = _truncate_text(
                document.body_text,
                self._max_tool_result_chars,
            )
            return {"source": payload}
        except SupplyChainAgentError:
            raise
        except Exception as error:
            raise SupplyChainAgentError(
                "SOURCE_TOOL_FAILED",
                retryable=bool(getattr(error, "retryable", False)),
            ) from None

    async def _invoke_structured[ResultT: BaseModel](
        self,
        *,
        schema: type[ResultT],
        stage: str,
        messages: list[BaseMessage],
        validator: OutputValidator[ResultT] | None = None,
        tool_count: int = 0,
    ) -> ResultT:
        provider_schema = _strict_output_schema(schema)
        try:
            runnable = self._model.with_structured_output(
                provider_schema,
                method="json_schema",
                strict=True,
                include_raw=True,
            )
        except Exception as error:
            raise SupplyChainAgentError.from_provider(error) from None
        attempt_messages = list(messages)
        provider_error: SupplyChainAgentError | None = None
        started = time.monotonic()
        for attempt in range(2):
            try:
                async with asyncio.timeout(self._stage_timeout_seconds):
                    raw_result = await runnable.ainvoke(attempt_messages)
                result, metadata = _parse_structured_result(schema, raw_result)
                if validator is not None:
                    validator(result)
                self._log_stage(
                    stage=stage,
                    duration=time.monotonic() - started,
                    tool_count=tool_count,
                    metadata=metadata,
                )
                return result
            except (ValidationError, ValueError):
                provider_error = None
            except SupplyChainAgentError as error:
                if error.code != "AGENT_OUTPUT_INVALID":
                    raise
                provider_error = None
            except Exception as error:
                provider_error = SupplyChainAgentError.from_provider(error)
                if not provider_error.retryable:
                    raise provider_error from None
            if attempt == 0:
                attempt_messages = [
                    *attempt_messages,
                    HumanMessage(
                        content=(
                            "The previous structured output failed validation. "
                            "Return a complete value matching the required schema."
                        )
                    ),
                ]
        if provider_error is not None:
            raise provider_error
        raise SupplyChainAgentError("AGENT_OUTPUT_INVALID")

    def _bounded_sources(
        self,
        sources: list[OfficialSourceDocument],
    ) -> list[dict[str, object]]:
        remaining = self._max_source_chars
        payloads: list[dict[str, object]] = []
        for index, source in enumerate(sources):
            source_count = len(sources) - index
            allocation = max(1, remaining // source_count)
            payload = source.model_dump(mode="json")
            payload["body_text"] = _truncate_text(source.body_text, allocation)
            remaining -= len(str(payload["body_text"]))
            payloads.append(payload)
        return payloads

    def _log_stage(
        self,
        *,
        stage: str,
        duration: float,
        tool_count: int,
        metadata: dict[str, object],
    ) -> None:
        logger.bind(
            model_id=self.model_id,
            stage=stage,
            duration_ms=round(duration * 1000),
            tool_count=tool_count,
            request_id=metadata.get("request_id"),
            input_tokens=metadata.get("input_tokens"),
            output_tokens=metadata.get("output_tokens"),
        ).info("Supply chain Agent stage completed")


def _parse_structured_result[ResultT: BaseModel](
    schema: type[ResultT],
    raw_result: Any,
) -> tuple[ResultT, dict[str, object]]:
    metadata: dict[str, object] = {}
    result = raw_result
    if isinstance(raw_result, dict) and "parsed" in raw_result:
        if raw_result.get("parsing_error") is not None:
            raise ValueError("structured parsing failed")
        result = raw_result.get("parsed")
        raw_message = raw_result.get("raw")
        response_metadata = getattr(raw_message, "response_metadata", {}) or {}
        usage_metadata = getattr(raw_message, "usage_metadata", {}) or {}
        metadata = {
            "request_id": response_metadata.get("id"),
            "input_tokens": usage_metadata.get("input_tokens"),
            "output_tokens": usage_metadata.get("output_tokens"),
        }
    return schema.model_validate(result), metadata


def _strict_output_schema(model: type[BaseModel]) -> dict[str, Any]:
    schema = model.model_json_schema()
    _require_all_schema_properties(schema)
    return schema


def _require_all_schema_properties(value: Any) -> None:
    if isinstance(value, list):
        for item in value:
            _require_all_schema_properties(item)
        return
    if not isinstance(value, dict):
        return
    value.pop("default", None)
    properties = value.get("properties")
    if isinstance(properties, dict):
        value["additionalProperties"] = False
        value["required"] = list(properties)
    for item in value.values():
        _require_all_schema_properties(item)


def _validate_source_plan(plan: SourcePlan, fetched_ids: set[str]) -> None:
    if not set(plan.selected_source_ids) <= fetched_ids:
        raise ValueError("source plan selected an unfetched source")


def _validate_draft(draft: GraphDraft, source_keys: set[str]) -> None:
    if any(
        node.aliases
        or node.resolution_status is not None
        or node.resolution_basis is not None
        for node in draft.nodes
    ):
        raise ValueError("model output included server-owned resolution audit")
    cited = {
        reference.source_key for edge in draft.edges for reference in edge.evidence_refs
    }
    if not cited <= source_keys:
        raise ValueError("draft cited an unknown source")


def _validate_verification(
    verification: GraphVerification,
    *,
    edge_keys: set[str],
    source_keys: set[str],
) -> None:
    returned_edges = {decision.edge_key for decision in verification.edge_verifications}
    if returned_edges != edge_keys:
        raise ValueError("verification edge membership is incomplete")
    cited = {
        reference.source_key
        for decision in verification.edge_verifications
        for reference in decision.evidence_refs
    }
    if not cited <= source_keys:
        raise ValueError("verification cited an unknown source")


def _truncate_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    if limit <= len(TRUNCATION_MARKER):
        return TRUNCATION_MARKER[:limit]
    return f"{value[: limit - len(TRUNCATION_MARKER)]}{TRUNCATION_MARKER}"


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
