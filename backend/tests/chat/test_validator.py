import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.chat.schemas import AnswerEvidencePack, ResearchAnswerPlan
from app.chat.validator import AnswerValidationError, validate_answer_plan

FIXTURES = Path(__file__).parents[1] / "fixtures" / "chat"


@pytest.fixture
def evidence_pack() -> AnswerEvidencePack:
    return AnswerEvidencePack.model_validate_json(
        (FIXTURES / "aapl_evidence.json").read_text()
    )


@pytest.fixture
def answers() -> dict[str, dict]:
    return json.loads((FIXTURES / "aapl_answers.json").read_text())


@pytest.mark.parametrize(
    ("fixture_name", "locale"),
    [("valid_en", "en-US"), ("valid_zh", "zh-CN")],
)
def test_valid_answer_plan_builds_ordered_immutable_citations(
    evidence_pack: AnswerEvidencePack,
    answers: dict[str, dict],
    fixture_name: str,
    locale: str,
) -> None:
    plan = ResearchAnswerPlan.model_validate(answers[fixture_name])

    validated = validate_answer_plan(plan, evidence_pack, locale=locale)

    assert validated.plan == plan
    assert [item.evidence_id for item in validated.citations] == plan.sources
    assert [item.ordinal for item in validated.citations] == list(
        range(len(plan.sources))
    )
    with pytest.raises(ValidationError):
        validated.citations[0].title = "changed"


def test_answer_schema_rejects_extra_fields_and_coerced_booleans(
    answers: dict[str, dict],
) -> None:
    extra = {**answers["valid_en"], "unexpected": "field"}
    coerced = {
        **answers["valid_en"],
        "web_search_used": "true",
    }

    with pytest.raises(ValidationError):
        ResearchAnswerPlan.model_validate(extra)
    with pytest.raises(ValidationError):
        ResearchAnswerPlan.model_validate(coerced)


@pytest.mark.parametrize(
    ("fixture_name", "message"),
    [
        ("invalid_citation", "unknown citation"),
        ("invalid_locale", "locale"),
        ("unsupported_number", "unsupported number"),
        ("unlabeled_inference", "inference must be labeled"),
    ],
)
def test_invalid_answer_claims_have_compact_validation_feedback(
    evidence_pack: AnswerEvidencePack,
    answers: dict[str, dict],
    fixture_name: str,
    message: str,
) -> None:
    plan = ResearchAnswerPlan.model_validate(answers[fixture_name])

    with pytest.raises(AnswerValidationError, match=message):
        validate_answer_plan(plan, evidence_pack, locale="en-US")


def test_sources_must_match_first_citation_order(
    evidence_pack: AnswerEvidencePack,
    answers: dict[str, dict],
) -> None:
    plan = ResearchAnswerPlan.model_validate(answers["valid_en"])
    reordered = plan.model_copy(update={"sources": list(reversed(plan.sources))})

    with pytest.raises(AnswerValidationError, match="source order"):
        validate_answer_plan(reordered, evidence_pack, locale="en-US")


@pytest.mark.parametrize("source_kind", ["filing", "web"])
def test_controlled_source_excerpt_must_match_archived_text(
    evidence_pack: AnswerEvidencePack,
    answers: dict[str, dict],
    source_kind: str,
) -> None:
    records = list(evidence_pack.records)
    index = next(
        position
        for position, record in enumerate(records)
        if record.candidate.source_kind == source_kind
    )
    record = records[index]
    records[index] = record.model_copy(
        update={
            "candidate": record.candidate.model_copy(
                update={"excerpt": "Altered excerpt absent from the archived text."}
            )
        }
    )
    altered = evidence_pack.model_copy(update={"records": records})
    plan = ResearchAnswerPlan.model_validate(answers["valid_en"])

    with pytest.raises(AnswerValidationError, match="excerpt mismatch"):
        validate_answer_plan(plan, altered, locale="en-US")


def test_cross_company_internal_evidence_is_rejected(
    evidence_pack: AnswerEvidencePack,
    answers: dict[str, dict],
) -> None:
    records = list(evidence_pack.records)
    records[0] = records[0].model_copy(update={"company_id": 2})
    cross_company = evidence_pack.model_copy(update={"records": records})
    plan = ResearchAnswerPlan.model_validate(answers["valid_en"])

    with pytest.raises(AnswerValidationError, match="cross-company evidence"):
        validate_answer_plan(plan, cross_company, locale="en-US")


def test_coverage_and_web_usage_follow_server_evidence_state(
    evidence_pack: AnswerEvidencePack,
    answers: dict[str, dict],
) -> None:
    with_gaps = evidence_pack.model_copy(
        update={"evidence_gaps": ["PEER_VALUATION_MISSING"]}
    )
    partial = ResearchAnswerPlan.model_validate(answers["partial"])
    insufficient = ResearchAnswerPlan.model_validate(answers["insufficient"])
    complete = ResearchAnswerPlan.model_validate(answers["valid_en"])

    assert validate_answer_plan(partial, with_gaps, locale="en-US").plan == partial
    assert (
        validate_answer_plan(insufficient, with_gaps, locale="en-US").plan
        == insufficient
    )
    with pytest.raises(AnswerValidationError, match="complete coverage"):
        validate_answer_plan(complete, with_gaps, locale="en-US")
    with pytest.raises(AnswerValidationError, match="web_search_used"):
        validate_answer_plan(
            complete.model_copy(update={"web_search_used": False}),
            evidence_pack,
            locale="en-US",
        )


def test_insufficient_answer_rejects_uncited_factual_conclusion(
    evidence_pack: AnswerEvidencePack,
    answers: dict[str, dict],
) -> None:
    with_gaps = evidence_pack.model_copy(
        update={"evidence_gaps": ["FILING_INDEX_MISSING"]}
    )
    plan = ResearchAnswerPlan.model_validate(answers["insufficient"])
    unsupported = plan.model_copy(
        update={
            "key_evidence": [
                plan.key_evidence[0].model_copy(
                    update={"text": "Apple dominates every relevant market."}
                )
            ]
        }
    )

    with pytest.raises(AnswerValidationError, match="unsupported insufficient"):
        validate_answer_plan(unsupported, with_gaps, locale="en-US")


def test_web_citation_snapshot_is_capped_at_six_hundred_characters(
    evidence_pack: AnswerEvidencePack,
) -> None:
    web = next(
        record
        for record in evidence_pack.records
        if record.candidate.source_kind == "web"
    )
    long_excerpt = "W" * 700
    records = [
        (
            record.model_copy(
                update={
                    "candidate": record.candidate.model_copy(
                        update={"excerpt": long_excerpt}
                    ),
                    "source_text": long_excerpt,
                }
            )
            if record == web
            else record
        )
        for record in evidence_pack.records
    ]
    pack = evidence_pack.model_copy(update={"records": records})
    plan = ResearchAnswerPlan.model_validate(
        {
            "direct_conclusion": {
                "text": "Regulatory evidence is available.",
                "citation_ids": [web.candidate.evidence_id],
            },
            "key_evidence": [
                {
                    "text": "The controlled page supports the conclusion.",
                    "citation_ids": [web.candidate.evidence_id],
                }
            ],
            "risks_and_uncertainties": [],
            "sources": [web.candidate.evidence_id],
            "evidence_coverage": "complete",
            "web_search_used": True,
        }
    )

    validated = validate_answer_plan(plan, pack, locale="en-US")

    assert len(validated.citations[0].excerpt) == 600
