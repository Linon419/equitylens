import asyncio
import json
from typing import Any

from loguru import logger
from pydantic import ValidationError

from app.chat.answer_recovery import (
    raw_message_content,
    recover_research_answer_plan,
)
from app.chat.contracts import AnswerPlanningModel, IntentRoutingModel
from app.chat.fallbacks import (
    fast_company_overview_route,
    fast_conversation_route,
    routing_fallback,
)
from app.chat.intents import AgentRouteDecision, IntentRoutingRequest
from app.chat.market_analysis_skills import MarketAnalysisSkill
from app.chat.prompts import AnswerPlanningRequest
from app.chat.schemas import AnswerEvidencePack, ResearchAnswerPlan


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
                parsing_error = result.get("parsing_error")
                if parsing_error is not None:
                    try:
                        recovered = recover_research_answer_plan(
                            raw_message_content(result.get("raw")),
                            request.evidence,
                        )
                    except (TypeError, ValueError, ValidationError):
                        logger.warning(
                            "Chat answer recovery failed for model {} after {}",
                            self.model_id,
                            type(parsing_error).__name__,
                        )
                        raise AnswerModelOutputError() from None
                    logger.warning(
                        "Chat answer schema recovered for model {} after {}",
                        self.model_id,
                        type(parsing_error).__name__,
                    )
                    return recovered
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
        overview_route = fast_company_overview_route(
            question,
            company_name=company_name,
            symbol=symbol,
            locale=locale,
        )
        if overview_route is not None:
            return overview_route
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
        analysis_skills: list[MarketAnalysisSkill] | None = None,
    ) -> ResearchAnswerPlan:
        try:
            async with asyncio.timeout(self._overall_timeout):
                return await self._create_model_plan(
                    question,
                    evidence,
                    locale=locale,
                    history=history,
                    analysis_skills=analysis_skills,
                )
        except TimeoutError:
            logger.warning(
                "Chat answer stage timed out for model {}",
                self.model_id,
            )
            raise AnswerProviderError() from None

    async def _create_model_plan(
        self,
        question: str,
        evidence: AnswerEvidencePack,
        *,
        locale: str,
        history: list[str] | None,
        analysis_skills: list[MarketAnalysisSkill] | None,
    ) -> ResearchAnswerPlan:
        request = AnswerPlanningRequest(
            question=question,
            locale=locale,
            evidence=evidence,
            history=history or [],
            analysis_skills=analysis_skills or [],
        )
        try:
            output = await self._model.plan(request)
            return ResearchAnswerPlan.model_validate(output)
        except (AnswerModelOutputError, ValidationError):
            logger.warning(
                "Chat answer schema failed for model {}",
                self.model_id,
            )
            raise AnswerModelOutputError() from None
        except AnswerProviderError:
            raise
        except Exception:
            logger.warning(
                "Chat answer provider failed for model {}",
                self.model_id,
            )
            raise AnswerProviderError() from None


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
