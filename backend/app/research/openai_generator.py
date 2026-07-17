import json
from typing import Any, TypeVar

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ValidationError

from app.research.output_normalizer import normalize_json_result
from app.research.prompts import (
    DRAFT_SYSTEM_PROMPT,
    LOCALIZE_SYSTEM_PROMPT,
    VERIFY_SYSTEM_PROMPT,
)
from app.research.schemas import (
    EvidenceBundle,
    IntelligenceDraft,
    Locale,
    LocalizedIntelligence,
    VerificationResult,
    VerifiedIntelligence,
)

StructuredResult = TypeVar("StructuredResult", bound=BaseModel)


class OpenAIIntelligenceGenerator:
    def __init__(
        self,
        model: ChatOpenAI,
        model_id: str,
        *,
        structured_output_method: str = "json_schema",
    ) -> None:
        self._model = model
        self.model_id = model_id
        self._structured_output_method = structured_output_method

    async def generate(self, bundle: EvidenceBundle) -> IntelligenceDraft:
        return await self._invoke(
            IntelligenceDraft,
            DRAFT_SYSTEM_PROMPT,
            bundle.model_dump_json(),
        )

    async def verify(self, draft: IntelligenceDraft) -> VerificationResult:
        return await self._invoke(
            VerificationResult,
            VERIFY_SYSTEM_PROMPT,
            draft.model_dump_json(),
        )

    async def localize(
        self,
        verified: VerifiedIntelligence,
        locale: Locale,
    ) -> LocalizedIntelligence:
        prompt = f"Target locale: {locale}\n{verified.model_dump_json()}"
        return await self._invoke(
            LocalizedIntelligence,
            LOCALIZE_SYSTEM_PROMPT,
            prompt,
        )

    async def _invoke(
        self,
        schema: type[StructuredResult],
        system_prompt: str,
        payload: str,
    ) -> StructuredResult:
        provider_schema: type[StructuredResult] | dict[str, Any] = schema
        if self._structured_output_method == "json_mode":
            provider_schema = schema.model_json_schema()
        structured = self._model.with_structured_output(
            provider_schema,
            method=self._structured_output_method,
        )
        messages = [
            ("system", self._structured_prompt(schema, system_prompt)),
            ("human", payload),
        ]
        for attempt in range(2):
            result: Any = await structured.ainvoke(messages)
            if self._structured_output_method == "json_mode":
                result = normalize_json_result(schema, result, payload)
            try:
                return schema.model_validate(result)
            except ValidationError as error:
                if (
                    self._structured_output_method != "json_mode"
                    or attempt == 1
                ):
                    raise
                messages.extend(self._repair_messages(result, error))
        raise RuntimeError("structured output validation exhausted")

    @staticmethod
    def _repair_messages(
        result: Any,
        error: ValidationError,
    ) -> list[tuple[str, str]]:
        validation_errors = json.dumps(
            error.errors(include_input=False, include_url=False),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return [
            ("assistant", json.dumps(result, ensure_ascii=False)),
            (
                "human",
                "Correct the JSON so it matches the required schema and the "
                "supplied evidence. Return only the complete corrected JSON. "
                f"Validation errors: {validation_errors}",
            ),
        ]

    def _structured_prompt(
        self,
        schema: type[StructuredResult],
        system_prompt: str,
    ) -> str:
        if self._structured_output_method != "json_mode":
            return system_prompt
        provider_schema = json.dumps(
            schema.model_json_schema(),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return (
            f"{system_prompt}\n"
            "Return only valid JSON matching this JSON Schema. "
            "Include every required property and no additional properties.\n"
            f"JSON Schema: {provider_schema}"
        )
