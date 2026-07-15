import json
from pathlib import Path

import pytest

from app.chat.schemas import (
    AnswerEvidencePack,
    AnswerPoint,
    ApprovedEvidenceRecord,
    ResearchAnswerPlan,
)
from app.chat.validator import validate_answer_plan

FIXTURE = Path(__file__).parents[1] / "fixtures" / "chat" / "rag-evaluation.json"


def load_evaluation() -> dict:
    return json.loads(FIXTURE.read_text())


CASES = load_evaluation()["questions"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_rag_evaluation_case(case: dict) -> None:
    evaluation = load_evaluation()
    records = {
        item["candidate"]["evidence_id"]: ApprovedEvidenceRecord.model_validate_json(
            json.dumps(item)
        )
        for item in evaluation["records"]
    }
    selected = [records[evidence_id] for evidence_id in case["evidence_ids"]]
    coverage = case["expected_coverage"][0]
    pack = AnswerEvidencePack(
        **evaluation["company"],
        records=selected,
        evidence_gaps=[] if coverage != "insufficient" else ["EVIDENCE_MISSING"],
        web_search_used=case["expected_web_search"],
    )
    plan = build_plan(case, selected, coverage)

    validated = validate_answer_plan(plan, pack, locale=case["locale"])

    assert pack.company_id == 1 and pack.symbol == "AAPL"
    assert validated.plan.evidence_coverage in case["expected_coverage"]
    assert validated.plan.web_search_used is case["expected_web_search"]
    assert {record.candidate.source_kind for record in selected} == set(
        case["required_source_kinds"]
    )
    assert [citation.evidence_id for citation in validated.citations] == case[
        "evidence_ids"
    ]
    assert_exact_support(case, selected, plan)
    assert_period(case, selected)


def build_plan(
    case: dict,
    records: list[ApprovedEvidenceRecord],
    coverage: str,
) -> ResearchAnswerPlan:
    if coverage == "insufficient":
        missing = "、".join(case["required_facts"])
        if case["locale"] == "zh-CN":
            conclusion = f"证据不足：缺少{missing}的可靠证据。"
            evidence_text = "所需证据缺失，当前无法形成可靠结论。"
        else:
            conclusion = (
                f"Insufficient evidence: reliable {missing} evidence is missing."
            )
            evidence_text = "The requested evidence is unavailable."
        return ResearchAnswerPlan(
            direct_conclusion=AnswerPoint(text=conclusion),
            key_evidence=[AnswerPoint(text=evidence_text)],
            evidence_coverage="insufficient",
            web_search_used=case["expected_web_search"],
        )

    first, *remaining = records
    evidence_points = remaining or [first]
    return ResearchAnswerPlan(
        direct_conclusion=AnswerPoint(
            text=first.candidate.excerpt,
            citation_ids=[first.candidate.evidence_id],
        ),
        key_evidence=[
            AnswerPoint(
                text=record.candidate.excerpt,
                citation_ids=[record.candidate.evidence_id],
            )
            for record in evidence_points
        ],
        sources=[record.candidate.evidence_id for record in records],
        evidence_coverage=coverage,
        web_search_used=case["expected_web_search"],
    )


def assert_exact_support(
    case: dict,
    records: list[ApprovedEvidenceRecord],
    plan: ResearchAnswerPlan,
) -> None:
    if plan.evidence_coverage == "insufficient":
        joined = f"{case['question']} {plan.direct_conclusion.text}".casefold()
        assert all(fact.casefold() in joined for fact in case["required_facts"])
        return
    source_text = " ".join(record.source_text for record in records)
    answer_text = " ".join(
        [plan.direct_conclusion.text, *(point.text for point in plan.key_evidence)]
    )
    assert all(record.candidate.excerpt in record.source_text for record in records)
    assert all(
        point.text in source_text
        for point in [plan.direct_conclusion, *plan.key_evidence]
    )
    assert all(
        fact.casefold() in answer_text.casefold()
        for fact in case["required_facts"]
    )


def assert_period(case: dict, records: list[ApprovedEvidenceRecord]) -> None:
    period = case.get("fiscal_period")
    if period is None:
        return
    assert any(
        period
        in {
            record.candidate.attributes.get("fiscal_period"),
            record.candidate.attributes.get("period_key"),
        }
        for record in records
    )
