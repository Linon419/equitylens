from dataclasses import dataclass

from app.chat.schemas import (
    AnswerEvidencePack,
    AnswerPoint,
    CitationSnapshot,
    EvidenceCandidate,
    ResearchAnswerPlan,
)


@dataclass(frozen=True, slots=True)
class BoundAnswer:
    plan: ResearchAnswerPlan
    citations: tuple[CitationSnapshot, ...]


def bind_answer_citations(
    plan: ResearchAnswerPlan,
    evidence: AnswerEvidencePack,
) -> BoundAnswer:
    approved = {
        record.candidate.evidence_id: record.candidate
        for record in evidence.records
        if _record_belongs_to_company(record.company_id, record.candidate, evidence)
    }
    points = [
        _bind_point(plan.direct_conclusion, approved),
        *(_bind_point(point, approved) for point in plan.key_evidence),
        *(_bind_point(point, approved) for point in plan.risks_and_uncertainties),
    ]
    direct = points[0]
    key_end = 1 + len(plan.key_evidence)
    key_evidence = points[1:key_end]
    risks = points[key_end:]
    sources = _approved_sources(plan.sources, points, approved)
    coverage = plan.evidence_coverage
    if evidence.evidence_gaps and coverage == "complete":
        coverage = "partial"
    bound_plan = plan.model_copy(
        update={
            "direct_conclusion": direct,
            "key_evidence": key_evidence,
            "risks_and_uncertainties": risks,
            "sources": sources,
            "evidence_coverage": coverage,
            "web_search_used": evidence.web_search_used,
        }
    )
    citations = tuple(
        _snapshot(approved[evidence_id], ordinal)
        for ordinal, evidence_id in enumerate(sources)
    )
    return BoundAnswer(bound_plan, citations)


def _record_belongs_to_company(
    company_id: int | None,
    candidate: EvidenceCandidate,
    evidence: AnswerEvidencePack,
) -> bool:
    return company_id == evidence.company_id or (
        company_id is None and candidate.source_kind == "web"
    )


def _bind_point(
    point: AnswerPoint,
    approved: dict[str, EvidenceCandidate],
) -> AnswerPoint:
    citation_ids = [
        evidence_id for evidence_id in point.citation_ids if evidence_id in approved
    ]
    return point.model_copy(update={"citation_ids": citation_ids})


def _approved_sources(
    requested: list[str],
    points: list[AnswerPoint],
    approved: dict[str, EvidenceCandidate],
) -> list[str]:
    sources: list[str] = []
    candidates = [*requested]
    candidates.extend(
        evidence_id for point in points for evidence_id in point.citation_ids
    )
    for evidence_id in candidates:
        if evidence_id in approved and evidence_id not in sources:
            sources.append(evidence_id)
    return sources


def _snapshot(candidate: EvidenceCandidate, ordinal: int) -> CitationSnapshot:
    excerpt_limit = 600 if candidate.source_kind == "web" else 1_000
    return CitationSnapshot(
        evidence_id=candidate.evidence_id,
        ordinal=ordinal,
        source_kind=candidate.source_kind,
        source_id=candidate.source_id,
        title=candidate.title,
        source_url=candidate.source_url,
        source_anchor=candidate.source_anchor,
        excerpt=candidate.excerpt[:excerpt_limit],
        published_at=candidate.published_at,
        retrieved_at=candidate.retrieved_at,
        source_tier=candidate.source_tier,
        verification=candidate.verification,
    )
