from typing import Any, TypeVar

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

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
    def __init__(self, model: ChatOpenAI, model_id: str) -> None:
        self._model = model
        self.model_id = model_id

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
        structured = self._model.with_structured_output(
            schema,
            method="json_schema",
        )
        result: Any = await structured.ainvoke(
            [("system", system_prompt), ("human", payload)]
        )
        return schema.model_validate(result)
