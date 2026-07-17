from copy import deepcopy
from typing import Any

import pytest
from pydantic import BaseModel

from app.research.openai_generator import OpenAIIntelligenceGenerator
from app.research.schemas import IntelligenceDraft
from app.research.validator import validate_draft_against_evidence


class ExampleResult(BaseModel):
    summary: str


class RecordingRunnable:
    def __init__(self, results: tuple[Any, ...]) -> None:
        self.messages: list[tuple[str, str]] = []
        self.results = results
        self.call_count = 0

    async def ainvoke(self, messages: list[tuple[str, str]]) -> Any:
        self.messages = messages
        result = self.results[min(self.call_count, len(self.results) - 1)]
        self.call_count += 1
        return result


class RecordingModel:
    def __init__(self, *results: Any) -> None:
        self.runnable = RecordingRunnable(results)
        self.calls: list[
            tuple[type[BaseModel] | dict[str, Any], dict[str, Any]]
        ] = []

    def with_structured_output(
        self,
        schema: type[BaseModel] | dict[str, Any],
        **options: Any,
    ) -> RecordingRunnable:
        self.calls.append((schema, options))
        return self.runnable


@pytest.mark.asyncio
async def test_json_mode_supplies_schema_in_the_system_prompt() -> None:
    model = RecordingModel({"summary": "verified"})
    generator = OpenAIIntelligenceGenerator(
        model,  # type: ignore[arg-type]
        "deepseek-v4-pro",
        structured_output_method="json_mode",
    )

    result = await generator._invoke(ExampleResult, "Analyze evidence.", "payload")

    assert result == ExampleResult(summary="verified")
    assert model.calls == [
        (ExampleResult.model_json_schema(), {"method": "json_mode"})
    ]
    system_prompt = model.runnable.messages[0][1]
    assert "Return only valid JSON matching this JSON Schema" in system_prompt
    assert '"summary"' in system_prompt


@pytest.mark.asyncio
async def test_json_mode_drops_unreferenced_citations(
    draft_payload: dict,
) -> None:
    response = deepcopy(draft_payload)
    expected_citation_ids = [
        citation["citation_id"] for citation in response["citations"]
    ]
    response["citations"].append(
        {
            "citation_id": "citation-999",
            "section_id": "section-risk",
            "excerpt": "Unused evidence remains outside the final claims.",
        }
    )
    model = RecordingModel(response)
    generator = OpenAIIntelligenceGenerator(
        model,  # type: ignore[arg-type]
        "deepseek-v4-pro",
        structured_output_method="json_mode",
    )

    result = await generator._invoke(
        IntelligenceDraft,
        "Analyze evidence.",
        "payload",
    )

    assert [
        citation.citation_id for citation in result.citations
    ] == expected_citation_ids
    assert model.runnable.call_count == 1


@pytest.mark.asyncio
async def test_json_mode_repairs_schema_validation_errors(
    draft_payload: dict,
) -> None:
    invalid = deepcopy(draft_payload)
    invalid["citations"][0]["excerpt"] = "Too short"
    model = RecordingModel(invalid, draft_payload)
    generator = OpenAIIntelligenceGenerator(
        model,  # type: ignore[arg-type]
        "deepseek-v4-pro",
        structured_output_method="json_mode",
    )

    result = await generator._invoke(
        IntelligenceDraft,
        "Analyze evidence.",
        "payload",
    )

    assert result == IntelligenceDraft.model_validate(draft_payload)
    assert model.runnable.call_count == 2
    repair_prompt = model.runnable.messages[-1][1]
    assert "Validation errors" in repair_prompt
    assert "string_too_short" in repair_prompt


@pytest.mark.asyncio
async def test_json_mode_expands_short_exact_citation_from_evidence(
    draft_payload: dict,
    evidence_bundle,
) -> None:
    response = deepcopy(draft_payload)
    response["citations"][0]["excerpt"] = "smartphones"
    model = RecordingModel(response)
    generator = OpenAIIntelligenceGenerator(
        model,  # type: ignore[arg-type]
        "deepseek-v4-pro",
        structured_output_method="json_mode",
    )

    result = await generator._invoke(
        IntelligenceDraft,
        "Analyze evidence.",
        evidence_bundle.model_dump_json(),
    )

    assert len(result.citations[0].excerpt) >= 20
    assert "smartphones" in result.citations[0].excerpt
    assert model.runnable.call_count == 1
    validate_draft_against_evidence(result, evidence_bundle)


@pytest.mark.asyncio
async def test_json_mode_drops_claims_with_paraphrased_citations(
    draft_payload: dict,
    evidence_bundle,
) -> None:
    response = deepcopy(draft_payload)
    response["citations"][0]["excerpt"] = (
        "This paraphrase does not occur in the supplied filing."
    )
    model = RecordingModel(response)
    generator = OpenAIIntelligenceGenerator(
        model,  # type: ignore[arg-type]
        "deepseek-v4-pro",
        structured_output_method="json_mode",
    )

    result = await generator._invoke(
        IntelligenceDraft,
        "Analyze evidence.",
        evidence_bundle.model_dump_json(),
    )

    assert result.core_businesses == []
    assert [citation.citation_id for citation in result.citations] == [
        "citation-2"
    ]
    assert model.runnable.call_count == 1
    validate_draft_against_evidence(result, evidence_bundle)
