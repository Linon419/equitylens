from typing import Any

from pydantic import ValidationError

from app.chat.contracts import AnswerPlanningModel
from app.chat.prompts import AnswerPlanningRequest
from app.chat.schemas import AnswerEvidencePack, ResearchAnswerPlan
from app.chat.validator import AnswerValidationError, validate_answer_plan
from app.core.errors import DomainError


class AnswerProviderError(RuntimeError):
    pass


class AnswerModelOutputError(ValueError):
    pass


class OpenAIResponsesPlanningModel:
    def __init__(
        self,
        client: Any,
        *,
        model_id: str,
        max_output_tokens: int = 8_000,
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


class CitationBoundAnswerAgent:
    def __init__(self, model: AnswerPlanningModel) -> None:
        self._model = model

    async def create_plan(
        self,
        question: str,
        evidence: AnswerEvidencePack,
        *,
        locale: str,
        history: list[str] | None = None,
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
                validate_answer_plan(plan, evidence, locale=locale)
                return plan
            except AnswerValidationError as error:
                feedback = error.repair_feedback
            except (AnswerModelOutputError, ValidationError) as error:
                feedback = _schema_feedback(error)
            except Exception:
                raise DomainError(
                    "CHAT_ANSWER_GENERATION_FAILED",
                    503,
                    {"retryable": True},
                ) from None
            if attempt == 1:
                break
        raise DomainError(
            "CHAT_ANSWER_VERIFICATION_FAILED",
            503,
            {"retryable": True},
        )


def _schema_feedback(error: Exception) -> str:
    if isinstance(error, ValidationError):
        messages = [
            f"{'.'.join(str(item) for item in detail['loc'])}: {detail['msg']}"
            for detail in error.errors(include_input=False)[:6]
        ]
        return "; ".join(messages)
    return "structured answer did not match the required schema"
