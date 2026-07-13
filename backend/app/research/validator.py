import re

from app.research.schemas import (
    CATEGORY_FIELDS,
    EvidenceBundle,
    IntelligenceDraft,
    LocalizedIntelligence,
    VerificationResult,
    VerifiedIntelligence,
)


def validate_draft_against_evidence(
    draft: IntelligenceDraft,
    evidence: EvidenceBundle,
) -> None:
    sections = {section.section_id: section for section in evidence.sections}
    for citation in draft.citations:
        section = sections.get(citation.section_id)
        if section is None:
            raise ValueError(
                f"citation {citation.citation_id} references unknown evidence section"
            )
        if _normalize(citation.excerpt) not in _normalize(section.text):
            raise ValueError(
                f"citation {citation.citation_id} excerpt is absent from evidence"
            )


def apply_verification(
    draft: IntelligenceDraft,
    verification: VerificationResult,
) -> VerifiedIntelligence:
    claim_ids = {claim.claim_id for claim in draft.all_claims()}
    verdicts = {verdict.claim_id: verdict for verdict in verification.verdicts}
    if set(verdicts) != claim_ids:
        raise ValueError("verification must contain one verdict for every claim")

    supported_ids = {
        claim_id for claim_id, verdict in verdicts.items() if verdict.supported
    }
    content = {
        field: [
            claim
            for claim in getattr(draft, field)
            if claim.claim_id in supported_ids
        ]
        for field in CATEGORY_FIELDS
    }
    citation_ids = {
        citation_id
        for claims in content.values()
        for claim in claims
        for citation_id in claim.citation_ids
    }
    citations = [
        citation
        for citation in draft.citations
        if citation.citation_id in citation_ids
    ]
    coverage = _coverage(len(supported_ids), len(claim_ids))
    confidence = _overall_confidence(content)
    return VerifiedIntelligence(
        **content,
        citations=citations,
        evidence_coverage=coverage,
        overall_confidence=confidence,
    )


def validate_localization_invariants(
    source: VerifiedIntelligence | LocalizedIntelligence,
    localized: LocalizedIntelligence,
) -> None:
    for field in CATEGORY_FIELDS:
        source_claims = getattr(source, field)
        localized_claims = getattr(localized, field)
        if len(source_claims) != len(localized_claims):
            raise ValueError("localization invariant changed category length")
        for original, translated in zip(
            source_claims,
            localized_claims,
            strict=True,
        ):
            invariant = (
                original.claim_id,
                original.confidence,
                original.citation_ids,
                original.revenue_share,
                original.revenue_period,
            )
            translated_invariant = (
                translated.claim_id,
                translated.confidence,
                translated.citation_ids,
                translated.revenue_share,
                translated.revenue_period,
            )
            if invariant != translated_invariant:
                raise ValueError("localization invariant changed claim metadata")
            if _numbers(original) != _numbers(translated):
                raise ValueError("localization invariant changed numeric content")
    if source.citations != localized.citations:
        raise ValueError("localization invariant changed citations")
    if (
        source.evidence_coverage != localized.evidence_coverage
        or source.overall_confidence != localized.overall_confidence
    ):
        raise ValueError("localization invariant changed verification metadata")


def _coverage(supported: int, total: int) -> str:
    if total == 0:
        return "insufficient_evidence"
    if supported == total:
        return "complete"
    if supported:
        return "partial"
    return "insufficient_evidence"


def _overall_confidence(content: dict) -> str | None:
    confidence_order = {"High": 2, "Medium": 1, "Low": 0}
    claims = [claim for values in content.values() for claim in values]
    if not claims:
        return None
    return min(
        (claim.confidence for claim in claims),
        key=confidence_order.__getitem__,
    )


def _numbers(content) -> set[str]:
    return set(
        re.findall(
            r"\d+(?:\.\d+)?",
            f"{content.title} {content.explanation}",
        )
    )


def _normalize(value: str) -> str:
    return " ".join(value.split())
