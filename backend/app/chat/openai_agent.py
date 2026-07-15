import asyncio
import json
from typing import Any

from loguru import logger
from pydantic import ValidationError

from app.chat.contracts import AnswerPlanningModel, IntentRoutingModel
from app.chat.fallbacks import (
    build_evidence_fallback,
    fast_conversation_route,
    routing_fallback,
)
from app.chat.intents import AgentRouteDecision, IntentRoutingRequest
from app.chat.prompts import AnswerPlanningRequest
from app.chat.schemas import AnswerEvidencePack, ResearchAnswerPlan
from app.chat.validator import (
    AnswerValidationError,
    normalize_answer_plan,
    validate_answer_plan,
)


class AnswerProviderError(RuntimeError):
    pass


class AnswerModelOutputError(ValueError):
    pass


class RoutingModelOutputError(ValueError):
    pass


class ChatCompletionsPlanningModel:
    def __init__(
        self,
        model: Any,
        *,
        model_id: str,
        structured_output_method: str = "json_schema",
    ) -> None:
        self._model = model
        self.model_id = model_id
        self._structured_output_method = structured_output_method

    async def plan(self, request: AnswerPlanningRequest) -> ResearchAnswerPlan:
        options: dict[str, Any] = {
            "method": self._structured_output_method,
            "include_raw": True,
        }
        if self._structured_output_method != "json_mode":
            options["strict"] = True
        messages = request.messages()
        if self._structured_output_method == "json_mode":
            messages = _with_json_schema(messages, ResearchAnswerPlan)
        try:
            runnable = self._model.with_structured_output(
                ResearchAnswerPlan,
                **options,
            )
            result = await runnable.ainvoke(messages)
            if isinstance(result, dict) and "parsed" in result:
                if result.get("parsing_error") is not None:
                    raise AnswerModelOutputError()
                result = result.get("parsed")
            return ResearchAnswerPlan.model_validate(result)
        except (AnswerModelOutputError, ValidationError):
            raise AnswerModelOutputError() from None
        except Exception:
            raise AnswerProviderError() from None


class OpenAIResponsesPlanningModel:
    def __init__(
        self,
        client: Any,
        *,
        model_id: str,
        max_output_tokens: int = 4_000,
    ) -> None:
        if max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")
        self._client = client
        self.model_id = model_id
        self._max_output_tokens = max_output_tokens

    async def plan(self, request: AnswerPlanningRequest) -> ResearchAnswerPlan:
        try:
            response = await self._client.responses.parse(
                model=self.model_id,
                input=request.messages(),
                text_format=ResearchAnswerPlan,
                max_output_tokens=self._max_output_tokens,
                store=False,
            )
        except ValidationError:
            raise AnswerModelOutputError() from None
        except Exception:
            raise AnswerProviderError() from None
        parsed = getattr(response, "output_parsed", None)
        if not isinstance(parsed, ResearchAnswerPlan):
            raise AnswerModelOutputError()
        return parsed


class ChatCompletionsRoutingModel:
    def __init__(
        self,
        model: Any,
        *,
        model_id: str,
        structured_output_method: str = "json_schema",
    ) -> None:
        self._model = model
        self.model_id = model_id
        self._structured_output_method = structured_output_method

    async def route(self, request: IntentRoutingRequest) -> AgentRouteDecision:
        options: dict[str, Any] = {
            "method": self._structured_output_method,
            "include_raw": True,
        }
        if self._structured_output_method != "json_mode":
            options["strict"] = True
        messages = request.messages()
        if self._structured_output_method == "json_mode":
            messages = _with_json_schema(messages, AgentRouteDecision)
        try:
            runnable = self._model.with_structured_output(
                AgentRouteDecision,
                **options,
            )
            result = await runnable.ainvoke(messages)
            if isinstance(result, dict) and "parsed" in result:
                if result.get("parsing_error") is not None:
                    raise RoutingModelOutputError()
                result = result.get("parsed")
            return AgentRouteDecision.model_validate(result)
        except (RoutingModelOutputError, ValidationError):
            raise RoutingModelOutputError() from None
        except Exception:
            raise AnswerProviderError() from None


class OpenAIResponsesRoutingModel:
    def __init__(
        self,
        client: Any,
        *,
        model_id: str,
        max_output_tokens: int = 1_000,
    ) -> None:
        self._client = client
        self.model_id = model_id
        self._max_output_tokens = max_output_tokens

    async def route(self, request: IntentRoutingRequest) -> AgentRouteDecision:
        try:
            response = await self._client.responses.parse(
                model=self.model_id,
                input=request.messages(),
                text_format=AgentRouteDecision,
                max_output_tokens=self._max_output_tokens,
                store=False,
            )
        except ValidationError:
            raise RoutingModelOutputError() from None
        except Exception:
            raise AnswerProviderError() from None
        parsed = getattr(response, "output_parsed", None)
        if not isinstance(parsed, AgentRouteDecision):
            raise RoutingModelOutputError()
        return parsed


class ModelDirectedIntentRouter:
    def __init__(
        self,
        model: IntentRoutingModel,
        *,
        overall_timeout: float = 15.0,
    ) -> None:
        if overall_timeout <= 0:
            raise ValueError("overall_timeout must be positive")
        self._model = model
        self.model_id = model.model_id
        self._overall_timeout = overall_timeout

    async def route(
        self,
        *,
        question: str,
        company_name: str,
        symbol: str,
        locale: str,
        history: list[str],
        summary: str | None = None,
    ) -> AgentRouteDecision:
        fast_route = fast_conversation_route(question, locale)
        if fast_route is not None:
            return fast_route
        request = IntentRoutingRequest(
            question=question,
            company_name=company_name,
            symbol=symbol,
            locale=locale,
            history=history,
            summary=summary,
        )
        try:
            async with asyncio.timeout(self._overall_timeout):
                for _ in range(2):
                    try:
                        return await self._model.route(request)
                    except Exception:
                        continue
        except TimeoutError:
            pass
        return routing_fallback(
            locale,
            question=question,
            is_follow_up=bool(history),
        )


class CitationBoundAnswerAgent:
    def __init__(
        self,
        model: AnswerPlanningModel,
        *,
        overall_timeout: float = 60.0,
    ) -> None:
        if overall_timeout <= 0:
            raise ValueError("overall_timeout must be positive")
        self._model = model
        self.model_id = getattr(model, "model_id", "unknown")
        self._overall_timeout = overall_timeout

    async def create_plan(
        self,
        question: str,
        evidence: AnswerEvidencePack,
        *,
        locale: str,
        history: list[str] | None = None,
    ) -> ResearchAnswerPlan:
        try:
            async with asyncio.timeout(self._overall_timeout):
                return await self._create_model_plan(
                    question,
                    evidence,
                    locale=locale,
                    history=history,
                )
        except TimeoutError:
            logger.warning(
                "Chat answer stage timed out for model {}",
                self.model_id,
            )
            return build_evidence_fallback(evidence, locale)

    async def _create_model_plan(
        self,
        question: str,
        evidence: AnswerEvidencePack,
        *,
        locale: str,
        history: list[str] | None,
    ) -> ResearchAnswerPlan:
        feedback: str | None = None
        for attempt in range(2):
            request = AnswerPlanningRequest(
                question=question,
                locale=locale,
                evidence=evidence,
                history=history or [],
                repair_feedback=feedback,
            )
            try:
                output = await self._model.plan(request)
                plan = ResearchAnswerPlan.model_validate(output)
                plan = normalize_answer_plan(plan, evidence, locale=locale)
                validate_answer_plan(plan, evidence, locale=locale)
                return plan
            except AnswerValidationError as error:
                logger.warning(
                    "Chat answer validation failed for model {} on attempt {}: {}",
                    self.model_id,
                    attempt + 1,
                    error.issues,
                )
                feedback = error.repair_feedback
            except (AnswerModelOutputError, ValidationError) as error:
                logger.warning(
                    "Chat answer schema failed for model {} on attempt {}: {}",
                    self.model_id,
                    attempt + 1,
                    type(error).__name__,
                )
                feedback = _schema_feedback(error)
            except Exception:
                logger.warning(
                    "Chat answer provider failed for model {}",
                    self.model_id,
                )
                return build_evidence_fallback(evidence, locale)
            if attempt == 1:
                break
        return build_evidence_fallback(evidence, locale)


def _schema_feedback(error: Exception) -> str:
    if isinstance(error, ValidationError):
        messages = [
            f"{'.'.join(str(item) for item in detail['loc'])}: {detail['msg']}"
            for detail in error.errors(include_input=False)[:6]
        ]
        return "; ".join(messages)
    return "structured answer did not match the required schema"


def _with_json_schema(
    messages: list[dict[str, str]],
    schema: type[ResearchAnswerPlan] | type[AgentRouteDecision],
) -> list[dict[str, str]]:
    instruction = {
        "role": "system",
        "content": (
            "Return only valid JSON matching this JSON Schema. Include every "
            "required property and no additional properties.\nJSON Schema: "
            + json.dumps(
                schema.model_json_schema(),
                ensure_ascii=False,
                separators=(",", ":"),
            )
        ),
    }
    if messages and messages[0]["role"] == "system":
        return [messages[0], instruction, *messages[1:]]
    return [instruction, *messages]
