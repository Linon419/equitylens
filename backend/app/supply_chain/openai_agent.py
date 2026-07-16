import asyncio
import json
import time
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager
from copy import deepcopy
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
from app.supply_chain.validator import validate_localization

type OutputValidator[ResultT: BaseModel] = Callable[[ResultT], None]
type OutputTransformer[ResultT: BaseModel] = Callable[[ResultT], ResultT]
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
        max_source_tokens: int = 100_000,
        max_tool_result_chars: int = 40_000,
        max_tool_calls: int = 8,
        token_counter: Callable[[str], int] | None = None,
        structured_output_method: str = "json_schema",
    ) -> None:
        if stage_timeout_seconds <= 0:
            raise ValueError("stage_timeout_seconds must be positive")
        if max_source_tokens < 1 or max_tool_result_chars < 64:
            raise ValueError("source limits are too small")
        if not 1 <= max_tool_calls <= 8:
            raise ValueError("max_tool_calls must be between one and eight")
        self._model = model
        self.model_id = model_id or getattr(model, "model_name", "unknown")
        self.schema_version = schema_version
        self.prompt_version = prompt_version
        self._stage_timeout_seconds = stage_timeout_seconds
        self._max_source_tokens = max_source_tokens
        self._max_tool_result_chars = max_tool_result_chars
        self._max_tool_calls = max_tool_calls
        self._structured_output_method = structured_output_method
        model_counter = getattr(model, "get_num_tokens", None)
        self._token_counter = token_counter or model_counter or _utf8_token_bound

    async def plan_sources(
        self,
        *,
        company: CompanyIdentity,
        tools: OfficialSourceTools,
    ) -> SourcePlan:
        async with self._stage_deadline():
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
            fetched_source_order: list[str] = []
            fetched_sources: dict[str, dict[str, object]] = {}
            tool_call_count = 0
            source_budget_exhausted = False
            source_tool_limit_reached = False

            def remember_source(result: dict[str, object]) -> None:
                source = result.get("source")
                if not isinstance(source, dict):
                    return
                source_id = source.get("source_id")
                if not isinstance(source_id, str):
                    return
                fetched_sources[source_id] = source
                if source_id not in fetched_source_order:
                    fetched_source_order.append(source_id)

            while True:
                response = await self._invoke_tool_model(bound, messages)
                messages.append(response)
                calls = response.tool_calls
                if not calls:
                    break
                if tool_call_count + len(calls) > self._max_tool_calls:
                    source_tool_limit_reached = True
                    remaining_calls = self._max_tool_calls - tool_call_count
                    calls = calls[: max(remaining_calls, 0)]
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
                    remember_source(result)
                    source_error = result.get("source_error")
                    if (
                        isinstance(source_error, dict)
                        and source_error.get("code")
                        == "SOURCE_RUN_BYTE_BUDGET_EXCEEDED"
                    ):
                        source_budget_exhausted = True
                        break
                if source_budget_exhausted:
                    break
                if source_tool_limit_reached:
                    break
            if source_tool_limit_reached and not fetched_ids:
                if not catalog:
                    fallback_sources = await tools.list_official_sources(
                        company=company,
                        query="suppliers products customers",
                        source_types=("sec_filing", "annual_report", "ir_page"),
                    )
                    catalog.update(
                        {source.source_id: source for source in fallback_sources}
                    )
                for metadata in list(catalog.values())[:3]:
                    try:
                        document = await tools.fetch_official_source(
                            source_id=metadata.source_id,
                        )
                    except Exception:
                        continue
                    fetched_ids.add(document.source_id)
                    remember_source({"source": document.model_dump(mode="json")})
            if not fetched_ids:
                raise SupplyChainAgentError("SOURCE_PLAN_EMPTY")
            final_messages: list[BaseMessage] = [
                SystemMessage(
                    content=(
                        f"{system_prompt}\n"
                        "Tool collection is complete. Return the final source plan "
                        "using only the fetched source IDs supplied below."
                    )
                ),
                HumanMessage(
                    content=_json(
                        {
                            "company": company_payload(company),
                            "fetched_sources": list(fetched_sources.values()),
                            "source_budget_exhausted": source_budget_exhausted,
                            "source_tool_limit_reached": source_tool_limit_reached,
                        }
                    )
                ),
            ]
            return await self._invoke_structured(
                schema=SourcePlan,
                stage="plan_sources",
                messages=final_messages,
                transformer=lambda result: _ensure_source_plan_coverage(
                    result,
                    fetched_source_order,
                ),
                validator=lambda result: _validate_source_plan(result, fetched_ids),
                tool_count=tool_call_count,
            )

    async def extract_graph(
        self,
        *,
        company: CompanyIdentity,
        sources: list[OfficialSourceDocument],
    ) -> GraphDraft:
        async with self._stage_deadline():
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
                transformer=lambda result: _sanitize_draft_source_refs(
                    result,
                    source_keys,
                ),
                validator=lambda result: _validate_draft(result, source_keys),
            )

    async def verify_graph(
        self,
        *,
        draft: GraphDraft,
        sources: list[OfficialSourceDocument],
    ) -> GraphVerification:
        async with self._stage_deadline():
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
        async with self._stage_deadline():
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
                validator=lambda result: validate_localization(
                    graph=graph,
                    localization=result,
                ),
            )

    @asynccontextmanager
    async def _stage_deadline(self) -> AsyncIterator[None]:
        try:
            async with asyncio.timeout(self._stage_timeout_seconds):
                yield
        except TimeoutError as error:
            raise SupplyChainAgentError.from_provider(error) from None

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
            result = await runnable.ainvoke(messages)
        except SupplyChainAgentError:
            raise
        except Exception as error:
            raise SupplyChainAgentError.from_provider(error) from None
        if not isinstance(result, AIMessage):
            raise SupplyChainAgentError("SOURCE_TOOL_RESPONSE_INVALID")
        self._log_provider_call(
            stage="plan_sources.tool",
            metadata=_message_metadata(result),
        )
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
            error_code = _safe_error_code(getattr(error, "code", None))
            retryable = bool(getattr(error, "retryable", False))
            logger.warning(
                "Supply chain Agent source tool failed: "
                "tool={} error_type={} error_code={} retryable={}",
                name,
                type(error).__name__,
                error_code,
                retryable,
            )
            if (
                name == "FetchOfficialSource"
                and isinstance(request, FetchOfficialSource)
                and error_code is not None
                and not retryable
            ):
                return {
                    "source_error": {
                        "source_id": request.source_id,
                        "code": error_code,
                        "retryable": False,
                    }
                }
            raise SupplyChainAgentError(
                "SOURCE_TOOL_FAILED",
                retryable=retryable,
            ) from None

    async def _invoke_structured[ResultT: BaseModel](
        self,
        *,
        schema: type[ResultT],
        stage: str,
        messages: list[BaseMessage],
        transformer: OutputTransformer[ResultT] | None = None,
        validator: OutputValidator[ResultT] | None = None,
        tool_count: int = 0,
    ) -> ResultT:
        provider_schema = _strict_output_schema(schema)
        try:
            structured_options: dict[str, Any] = {
                "method": self._structured_output_method,
                "include_raw": True,
            }
            if self._structured_output_method != "json_mode":
                structured_options["strict"] = True
            runnable = self._model.with_structured_output(
                provider_schema,
                **structured_options,
            )
        except Exception as error:
            raise SupplyChainAgentError.from_provider(error) from None
        attempt_messages = self._structured_messages(messages, provider_schema)
        provider_error: SupplyChainAgentError | None = None
        repair_instruction = _structured_repair_instruction()
        started = time.monotonic()
        for attempt in range(2):
            raw_result: Any = None
            try:
                raw_result = await runnable.ainvoke(attempt_messages)
                result, metadata = _parse_structured_result(schema, raw_result)
                if transformer is not None:
                    result = transformer(result)
                if validator is not None:
                    validator(result)
                self._log_stage(
                    stage=stage,
                    duration=time.monotonic() - started,
                    tool_count=tool_count,
                    metadata=metadata,
                )
                return result
            except (ValidationError, ValueError) as error:
                self._log_output_failure(
                    stage=stage,
                    attempt=attempt + 1,
                    error=error,
                    raw_result=raw_result,
                )
                repair_instruction = _structured_repair_instruction(error)
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
                    HumanMessage(content=repair_instruction),
                ]
        if provider_error is not None:
            raise provider_error
        raise SupplyChainAgentError("AGENT_OUTPUT_INVALID")

    def _structured_messages(
        self,
        messages: list[BaseMessage],
        provider_schema: dict[str, Any],
    ) -> list[BaseMessage]:
        if self._structured_output_method != "json_mode":
            return list(messages)
        instruction = SystemMessage(
            content=(
                "Return only valid JSON matching this JSON Schema. "
                "Include every required property and no additional properties.\n"
                f"JSON Schema: {_json(provider_schema)}"
            )
        )
        if messages and isinstance(messages[0], SystemMessage):
            return [messages[0], instruction, *messages[1:]]
        return [instruction, *messages]

    def _log_output_failure(
        self,
        *,
        stage: str,
        attempt: int,
        error: ValidationError | ValueError,
        raw_result: Any,
    ) -> None:
        raw_message = (
            raw_result.get("raw")
            if isinstance(raw_result, dict)
            else None
        )
        metadata = _message_metadata(raw_message)
        logger.warning(
            "Supply chain Agent structured output rejected: "
            "stage={} attempt={} issues={} finish_reason={} output_tokens={}",
            stage,
            attempt,
            _validation_issue_summary(error),
            metadata.get("finish_reason"),
            metadata.get("output_tokens"),
        )

    def _bounded_sources(
        self,
        sources: list[OfficialSourceDocument],
    ) -> list[dict[str, object]]:
        remaining = self._max_source_tokens
        payloads: list[dict[str, object]] = []
        for index, source in enumerate(sources):
            source_count = len(sources) - index
            allocation = remaining // source_count
            payload = source.model_dump(mode="json")
            payload["body_text"] = _truncate_to_tokens(
                source.body_text,
                allocation,
                self._token_counter,
            )
            remaining = max(
                0,
                remaining - self._token_counter(str(payload["body_text"])),
            )
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
            finish_reason=metadata.get("finish_reason"),
        ).info("Supply chain Agent stage completed")

    def _log_provider_call(
        self,
        *,
        stage: str,
        metadata: dict[str, object],
    ) -> None:
        logger.bind(
            model_id=self.model_id,
            stage=stage,
            request_id=metadata.get("request_id"),
            input_tokens=metadata.get("input_tokens"),
            output_tokens=metadata.get("output_tokens"),
            finish_reason=metadata.get("finish_reason"),
        ).info("Supply chain Agent provider call completed")


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
        metadata = _message_metadata(raw_message)
    result = _normalize_provider_result(schema, result)
    return schema.model_validate(result), metadata


def _message_metadata(message: Any) -> dict[str, object]:
    response_metadata = getattr(message, "response_metadata", {}) or {}
    usage_metadata = getattr(message, "usage_metadata", {}) or {}
    return {
        "request_id": response_metadata.get("id"),
        "input_tokens": usage_metadata.get("input_tokens"),
        "output_tokens": usage_metadata.get("output_tokens"),
        "finish_reason": response_metadata.get("finish_reason"),
    }


def _normalize_provider_result(
    schema: type[BaseModel],
    result: Any,
) -> Any:
    if schema is not GraphDraft or not isinstance(result, dict):
        return result
    normalized = deepcopy(result)
    for node in normalized.get("nodes", []):
        if not isinstance(node, dict):
            continue
        label = node.get("label_en")
        seen = {label.casefold()} if isinstance(label, str) else set()
        aliases: list[str] = []
        for alias in node.get("aliases", []):
            if not isinstance(alias, str) or alias.casefold() in seen:
                continue
            seen.add(alias.casefold())
            aliases.append(alias)
        node["aliases"] = aliases
        node["resolution_status"] = None
        node["resolution_basis"] = None
    for edge in normalized.get("edges", []):
        if not isinstance(edge, dict):
            continue
        references: list[dict[str, Any]] = []
        seen_references: set[tuple[object, ...]] = set()
        for reference in edge.get("evidence_refs", []):
            if not isinstance(reference, dict):
                continue
            identity = tuple(
                reference.get(field)
                for field in (
                    "source_key",
                    "excerpt",
                    "locator",
                    "support_role",
                )
            )
            if identity in seen_references:
                continue
            seen_references.add(identity)
            references.append(reference)
        edge["evidence_refs"] = references
    return normalized


def _validation_issue_summary(error: ValidationError | ValueError) -> str:
    if not isinstance(error, ValidationError):
        return "semantic_or_parse_error"
    issues = [
        str(issue.get("type", "validation_error"))
        for issue in error.errors(include_input=False)[:8]
    ]
    return ",".join(issues) or "validation_error"


def _structured_repair_instruction(
    error: ValidationError | ValueError | None = None,
) -> str:
    lines = [
        "The previous structured output failed validation.",
        "Return the complete JSON value again and satisfy every schema constraint.",
    ]
    if isinstance(error, ValueError):
        lines.append(f"Validation issue: {str(error)[:240]}")
    if not isinstance(error, ValidationError):
        return " ".join(lines)
    lines.append("Correct these validation issues:")
    for issue in error.errors(include_input=False)[:8]:
        location = ".".join(str(part) for part in issue.get("loc", ())) or "$"
        issue_type = str(issue.get("type", "validation_error"))
        message = str(issue.get("msg", "invalid value"))
        lines.append(f"- {location}: {issue_type} ({message})")
    return "\n".join(lines)


def _safe_error_code(value: Any) -> str | None:
    if not isinstance(value, str) or not 1 <= len(value) <= 64:
        return None
    allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
    if any(character not in allowed for character in value):
        return None
    return value


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


def _ensure_source_plan_coverage(
    plan: SourcePlan,
    fetched_source_order: Sequence[str],
) -> SourcePlan:
    selected = list(plan.selected_source_ids)
    for source_id in fetched_source_order:
        if source_id in selected:
            continue
        if len(selected) >= 6:
            break
        selected.append(source_id)
    if selected == plan.selected_source_ids:
        return plan
    return plan.model_copy(update={"selected_source_ids": selected})


def _validate_draft(draft: GraphDraft, source_keys: set[str]) -> None:
    if len(draft.nodes) < 12:
        raise ValueError("draft must include at least 12 nodes")
    if len(draft.edges) < 11:
        raise ValueError("draft must include at least 11 edges")
    if any(
        node.resolution_status is not None or node.resolution_basis is not None
        for node in draft.nodes
    ):
        raise ValueError("model output included server-owned resolution audit")
    cited = {
        reference.source_key for edge in draft.edges for reference in edge.evidence_refs
    }
    if not cited <= source_keys:
        raise ValueError("draft cited an unknown source")


def _sanitize_draft_source_refs(
    draft: GraphDraft,
    source_keys: set[str],
) -> GraphDraft:
    payload = draft.model_dump(mode="json")
    for edge in payload["edges"]:
        edge["evidence_refs"] = [
            reference
            for reference in edge["evidence_refs"]
            if reference["source_key"] in source_keys
        ]
        if edge["evidence_status"] in {"verified", "potential"} and not edge[
            "evidence_refs"
        ]:
            edge["evidence_status"] = "internal"
    return GraphDraft.model_validate(payload)


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


def _truncate_to_tokens(
    value: str,
    limit: int,
    count_tokens: Callable[[str], int],
) -> str:
    if count_tokens(value) <= limit:
        return value
    if count_tokens(TRUNCATION_MARKER) > limit:
        return ""
    low = 0
    high = len(value)
    candidate = TRUNCATION_MARKER
    while low <= high:
        midpoint = (low + high) // 2
        proposed = f"{value[:midpoint]}{TRUNCATION_MARKER}"
        if count_tokens(proposed) <= limit:
            candidate = proposed
            low = midpoint + 1
        else:
            high = midpoint - 1
    while candidate and count_tokens(candidate) > limit:
        candidate = candidate[:-1]
    return candidate


def _utf8_token_bound(value: str) -> int:
    return len(value.encode("utf-8"))


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
