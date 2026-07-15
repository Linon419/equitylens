import re
from dataclasses import dataclass

from app.chat.schemas import (
    AnswerEvidencePack,
    AnswerPoint,
    ApprovedEvidenceRecord,
    CitationSnapshot,
    EvidenceCandidate,
    ResearchAnswerPlan,
)

_MISSING_MARKERS = (
    "insufficient",
    "missing",
    "unavailable",
    "缺少",
    "缺失",
    "无法",
    "证据不足",
)


class AnswerValidationError(ValueError):
    def __init__(self, issues: list[str]) -> None:
        self.issues = tuple(issues[:8])
        super().__init__("; ".join(self.issues))

    @property
    def repair_feedback(self) -> str:
        issues = "; ".join(issue[:180] for issue in self.issues)
        return (
            "Regenerate the complete answer plan. Every answer point must use "
            "approved citation IDs. Use only numbers found literally in each "
            "cited candidate.excerpt. Omit unsupported risks, dates, and numeric "
            "details. Preserve exact first-appearance source order. Validator "
            f"issues: {issues}"
        )


@dataclass(frozen=True, slots=True)
class ValidatedAnswer:
    plan: ResearchAnswerPlan
    citations: tuple[CitationSnapshot, ...]


def normalize_answer_plan(
    plan: ResearchAnswerPlan,
    evidence: AnswerEvidencePack,
    *,
    locale: str,
) -> ResearchAnswerPlan:
    direct = _normalize_point(plan.direct_conclusion, locale)
    key_evidence = [_normalize_point(point, locale) for point in plan.key_evidence]
    risks = [
        _normalize_point(point, locale)
        for point in plan.risks_and_uncertainties
    ]
    points = [direct, *key_evidence, *risks]
    return plan.model_copy(
        update={
            "direct_conclusion": direct,
            "key_evidence": key_evidence,
            "risks_and_uncertainties": risks,
            "sources": _ordered_references(points),
            "web_search_used": evidence.web_search_used,
        }
    )


def validate_answer_plan(
    plan: ResearchAnswerPlan,
    evidence: AnswerEvidencePack,
    *,
    locale: str,
) -> ValidatedAnswer:
    records = {record.candidate.evidence_id: record for record in evidence.records}
    issues = _validate_evidence(evidence)
    points = [
        plan.direct_conclusion,
        *plan.key_evidence,
        *plan.risks_and_uncertainties,
    ]
    references = _ordered_references(points)
    unknown = [evidence_id for evidence_id in references if evidence_id not in records]
    if unknown:
        issues.append(f"unknown citation: {unknown[0]}")
    if plan.sources != references:
        issues.append("source order must match first citation appearance")
    if plan.web_search_used != evidence.web_search_used:
        issues.append("web_search_used must match server evidence state")
    _validate_coverage(plan, evidence, issues)
    _validate_points(plan, points, records, locale, issues)
    if issues:
        raise AnswerValidationError(issues)
    citations = tuple(
        _snapshot(records[evidence_id].candidate, ordinal)
        for ordinal, evidence_id in enumerate(plan.sources)
    )
    return ValidatedAnswer(plan, citations)


def _validate_evidence(evidence: AnswerEvidencePack) -> list[str]:
    issues: list[str] = []
    for record in evidence.records:
        candidate = record.candidate
        if record.company_id not in {None, evidence.company_id}:
            issues.append(f"cross-company evidence: {candidate.evidence_id}")
        if record.company_id is None and candidate.source_kind != "web":
            issues.append(f"unowned internal evidence: {candidate.evidence_id}")
        if candidate.source_kind in {"filing", "web"} and _normalize(
            candidate.excerpt
        ) not in _normalize(record.source_text):
            issues.append(f"excerpt mismatch: {candidate.evidence_id}")
        if candidate.source_kind == "web":
            artifact_hash = candidate.attributes.get("artifact_sha256")
            if not isinstance(artifact_hash, str) or re.fullmatch(
                r"[0-9a-f]{64}", artifact_hash
            ) is None:
                issues.append(
                    "web artifact verification missing: " f"{candidate.evidence_id}"
                )
    return issues


def _validate_coverage(
    plan: ResearchAnswerPlan,
    evidence: AnswerEvidencePack,
    issues: list[str],
) -> None:
    if evidence.evidence_gaps and plan.evidence_coverage == "complete":
        issues.append("complete coverage is invalid while evidence gaps remain")
    if plan.evidence_coverage == "insufficient":
        if not evidence.evidence_gaps:
            issues.append("insufficient coverage requires an evidence gap")
        if not any(
            marker in plan.direct_conclusion.text.casefold()
            for marker in _MISSING_MARKERS
        ):
            issues.append("insufficient answer must identify missing evidence")


def _validate_points(
    plan: ResearchAnswerPlan,
    points: list[AnswerPoint],
    records: dict[str, ApprovedEvidenceRecord],
    locale: str,
    issues: list[str],
) -> None:
    for index, point in enumerate(points):
        label = f"answer point {index + 1}"
        if plan.evidence_coverage != "insufficient" and not point.citation_ids:
            issues.append(f"{label} requires a citation")
        if (
            plan.evidence_coverage == "insufficient"
            and not point.citation_ids
            and not any(marker in point.text.casefold() for marker in _MISSING_MARKERS)
        ):
            issues.append(f"{label} has an unsupported insufficient conclusion")
        if point.inference and not _inference_is_labeled(point.text, locale):
            issues.append(f"{label} inference must be labeled")
        if not point.inference and _looks_inferential(point.text):
            issues.append(f"{label} inference must be labeled")
        if point.inference and not point.citation_ids:
            issues.append(f"{label} inference requires cited premises")
        if not _matches_locale(point.text, locale):
            issues.append(f"{label} does not match locale {locale}")
        cited = [records[item] for item in point.citation_ids if item in records]
        supported_numbers = {
            number
            for record in cited
            for number in _numbers(record.candidate.excerpt)
        }
        unsupported = _numbers(point.text) - supported_numbers
        if unsupported:
            issues.append(f"{label} has unsupported number: {sorted(unsupported)[0]}")


def _normalize_point(point: AnswerPoint, locale: str) -> AnswerPoint:
    inference = (
        point.inference
        or _looks_inferential(point.text)
        or _inference_is_labeled(point.text, locale)
    )
    if not inference or _inference_is_labeled(point.text, locale):
        return point.model_copy(update={"inference": inference})
    prefix = "推断：" if locale == "zh-CN" else "Inference: "
    return point.model_copy(
        update={"text": f"{prefix}{point.text}", "inference": True}
    )


def _ordered_references(points: list[AnswerPoint]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for point in points:
        for evidence_id in point.citation_ids:
            if evidence_id not in seen:
                seen.add(evidence_id)
                ordered.append(evidence_id)
    return ordered


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


def _normalize(value: str) -> str:
    return " ".join(value.split())


def _numbers(value: str) -> set[str]:
    return {
        match.replace(",", "")
        for match in re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?%?", value)
    }


def _inference_is_labeled(value: str, locale: str) -> bool:
    stripped = value.strip()
    if locale == "zh-CN":
        return stripped.startswith(("推断：", "推断:"))
    return stripped.casefold().startswith("inference:")


def _looks_inferential(value: str) -> bool:
    return re.search(
        r"\b(may|might|could|likely|suggests|implies)\b|可能|或许|推测",
        value,
        re.IGNORECASE,
    ) is not None


def _matches_locale(value: str, locale: str) -> bool:
    has_cjk = re.search(r"[\u3400-\u9fff]", value) is not None
    return has_cjk if locale == "zh-CN" else not has_cjk
