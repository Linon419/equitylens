import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.chat.citation_binding import bind_answer_citations
from app.chat.schemas import AnswerEvidencePack, ResearchAnswerPlan

FIXTURES = Path(__file__).parents[1] / "fixtures" / "chat"


@pytest.fixture
def evidence_pack() -> AnswerEvidencePack:
    return AnswerEvidencePack.model_validate_json(
        (FIXTURES / "aapl_evidence.json").read_text()
    )


@pytest.fixture
def answers() -> dict[str, dict]:
    return json.loads((FIXTURES / "aapl_answers.json").read_text())


def test_unknown_citations_are_filtered_without_replacing_the_answer(
    evidence_pack: AnswerEvidencePack,
    answers: dict[str, dict],
) -> None:
    plan = ResearchAnswerPlan.model_validate(answers["invalid_citation"])

    bound = bind_answer_citations(plan, evidence_pack)

    assert bound.plan.direct_conclusion.text == "Apple has a supported conclusion."
    assert bound.plan.direct_conclusion.citation_ids == []
    assert bound.plan.key_evidence[0].citation_ids == ["graph:tsmc-supplies-apple"]
    assert bound.plan.sources == ["graph:tsmc-supplies-apple"]
    assert [item.evidence_id for item in bound.citations] == [
        "graph:tsmc-supplies-apple"
    ]


def test_binding_preserves_model_numbers_and_natural_inference_language(
    evidence_pack: AnswerEvidencePack,
    answers: dict[str, dict],
) -> None:
    numeric = ResearchAnswerPlan.model_validate(answers["unsupported_number"])
    inference = ResearchAnswerPlan.model_validate(answers["unlabeled_inference"])

    bound_numeric = bind_answer_citations(numeric, evidence_pack)
    bound_inference = bind_answer_citations(inference, evidence_pack)

    assert "999 billion USD" in bound_numeric.plan.direct_conclusion.text
    assert bound_inference.plan.risks_and_uncertainties[0].text == (
        "Regulatory scrutiny may increase compliance risk."
    )
    assert bound_inference.plan.risks_and_uncertainties[0].inference is False


def test_server_owned_coverage_and_web_state_are_applied(
    evidence_pack: AnswerEvidencePack,
    answers: dict[str, dict],
) -> None:
    evidence = evidence_pack.model_copy(
        update={
            "evidence_gaps": ["CHAT_WEB_SEARCH_UNAVAILABLE"],
            "web_search_used": False,
        }
    )
    plan = ResearchAnswerPlan.model_validate(answers["valid_en"])

    bound = bind_answer_citations(plan, evidence)

    assert bound.plan.evidence_coverage == "partial"
    assert bound.plan.web_search_used is False


def test_citation_snapshots_remain_bounded_and_immutable(
    evidence_pack: AnswerEvidencePack,
    answers: dict[str, dict],
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
    evidence = evidence_pack.model_copy(update={"records": records})
    plan = ResearchAnswerPlan.model_validate(answers["valid_en"])

    bound = bind_answer_citations(plan, evidence)
    citation = next(item for item in bound.citations if item.source_kind == "web")

    assert len(citation.excerpt) == 600
    with pytest.raises(ValidationError):
        citation.title = "changed"
