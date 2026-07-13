from datetime import UTC, datetime
from typing import Protocol

from sqlmodel import Session, select

from app.core.errors import DomainError
from app.models.company_model import Company
from app.models.research_model import (
    CompanyIntelligenceSnapshot,
    EvidenceCitation,
    Filing,
    FilingSection,
)
from app.research.schemas import (
    CitationDraft,
    EvidenceBundle,
    EvidenceSection,
    IntelligenceDraft,
    IntelligenceResponse,
    Locale,
    LocalizedIntelligence,
    PublicCitation,
    VerificationResult,
    VerifiedIntelligence,
)
from app.research.validator import (
    apply_verification,
    validate_draft_against_evidence,
    validate_localization_invariants,
)


class IntelligenceGenerator(Protocol):
    model_id: str

    async def generate(self, bundle: EvidenceBundle) -> IntelligenceDraft: ...

    async def verify(self, draft: IntelligenceDraft) -> VerificationResult: ...

    async def localize(
        self,
        verified: VerifiedIntelligence,
        locale: Locale,
    ) -> LocalizedIntelligence: ...


def get_public_intelligence(
    session: Session,
    company: Company,
    locale: Locale,
) -> IntelligenceResponse:
    snapshot = session.exec(
        select(CompanyIntelligenceSnapshot)
        .where(
            CompanyIntelligenceSnapshot.company_id == company.id,
            CompanyIntelligenceSnapshot.status == "completed",
        )
        .order_by(CompanyIntelligenceSnapshot.generated_at.desc())
    ).first()
    if snapshot is None:
        raise DomainError("INTELLIGENCE_NOT_FOUND", 404)
    filing = session.get(Filing, snapshot.filing_id)
    if filing is None:
        raise DomainError("FILING_NOT_FOUND", 404)
    payload = snapshot.content_en if locale == "en" else snapshot.content_zh
    if payload is None:
        raise DomainError("INTELLIGENCE_LOCALE_UNAVAILABLE", 404)
    content = LocalizedIntelligence.model_validate(payload)
    rows = session.exec(
        select(FilingSection).where(FilingSection.filing_id == filing.id)
    ).all()
    sections = {str(row.id): row for row in rows}
    citations = []
    for citation in content.citations:
        section = sections.get(citation.section_id)
        if section is None:
            raise DomainError("INTELLIGENCE_CITATION_INVALID", 500)
        citations.append(
            PublicCitation(
                id=citation.citation_id,
                filing_date=filing.filed_at,
                section=section.heading,
                source_anchor=section.source_anchor,
                excerpt=citation.excerpt,
                source_url=f"{filing.source_url}#{section.source_anchor}",
            )
        )
    return IntelligenceResponse(
        snapshot_id=str(snapshot.id),
        symbol=company.symbol,
        filing_date=filing.filed_at,
        filing_url=filing.source_url,
        evidence_coverage=content.evidence_coverage,
        overall_confidence=content.overall_confidence,
        model_id=snapshot.model_id,
        generated_at=snapshot.generated_at,
        content=content,
        citations=citations,
    )


async def generate_draft(
    session: Session,
    company: Company,
    filing: Filing,
    generator: IntelligenceGenerator,
    *,
    schema_version: str,
    prompt_version: str,
    now: datetime | None = None,
) -> CompanyIntelligenceSnapshot:
    snapshot = _find_snapshot(
        session,
        company,
        filing,
        generator.model_id,
        schema_version,
        prompt_version,
    )
    if (
        snapshot is not None
        and snapshot.status in {"drafted", "verified", "completed"}
        and snapshot.content_en is not None
    ):
        return snapshot

    current_time = now or datetime.now(UTC)
    evidence = _build_evidence_bundle(session, company, filing)
    draft = await generator.generate(evidence)
    validate_draft_against_evidence(draft, evidence)

    if snapshot is None:
        snapshot = CompanyIntelligenceSnapshot(
            company_id=company.id,
            filing_id=filing.id,
            status="drafted",
            evidence_coverage="partial",
            schema_version=schema_version,
            prompt_version=prompt_version,
            model_id=generator.model_id,
            generated_at=current_time,
        )
    snapshot.status = "drafted"
    snapshot.content_en = draft.model_dump(mode="json")
    snapshot.content_zh = None
    snapshot.generated_at = current_time
    snapshot.verified_at = None
    snapshot.overall_confidence = None
    session.add(snapshot)
    session.flush()
    _replace_citations(
        session,
        snapshot,
        filing,
        evidence,
        draft.citations,
        "pending",
    )
    session.commit()
    session.refresh(snapshot)
    return snapshot


async def verify_snapshot(
    session: Session,
    snapshot: CompanyIntelligenceSnapshot,
    generator: IntelligenceGenerator,
    *,
    now: datetime | None = None,
) -> CompanyIntelligenceSnapshot:
    if snapshot.status in {"verified", "completed"}:
        return snapshot
    if snapshot.content_en is None:
        raise DomainError("INTELLIGENCE_DRAFT_MISSING", 409)

    draft = IntelligenceDraft.model_validate(snapshot.content_en)
    verification = await generator.verify(draft)
    verified = apply_verification(draft, verification)
    current_time = now or datetime.now(UTC)
    snapshot.content_en = verified.model_dump(mode="json")
    snapshot.evidence_coverage = verified.evidence_coverage
    snapshot.overall_confidence = verified.overall_confidence
    snapshot.verified_at = current_time
    if verified.evidence_coverage == "insufficient_evidence":
        snapshot.status = "failed"
        session.add(snapshot)
        session.commit()
        raise DomainError("INSUFFICIENT_EVIDENCE", 422)

    snapshot.status = "verified"
    filing = session.get(Filing, snapshot.filing_id)
    if filing is None:
        raise DomainError("FILING_NOT_FOUND", 404)
    company = session.get(Company, snapshot.company_id)
    if company is None:
        raise DomainError("COMPANY_NOT_FOUND", 404)
    evidence = _build_evidence_bundle(session, company, filing)
    _replace_citations(
        session,
        snapshot,
        filing,
        evidence,
        verified.citations,
        "supported",
    )
    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)
    return snapshot


async def localize_snapshot(
    session: Session,
    snapshot: CompanyIntelligenceSnapshot,
    generator: IntelligenceGenerator,
) -> CompanyIntelligenceSnapshot:
    if snapshot.status == "completed":
        return snapshot
    if snapshot.status != "verified" or snapshot.content_en is None:
        raise DomainError("INTELLIGENCE_NOT_VERIFIED", 409)

    verified = VerifiedIntelligence.model_validate(snapshot.content_en)
    english = await generator.localize(verified, "en")
    if english.locale != "en":
        raise ValueError("English localization returned the wrong locale")
    validate_localization_invariants(verified, english)
    chinese = await generator.localize(verified, "zh")
    if chinese.locale != "zh":
        raise ValueError("Chinese localization returned the wrong locale")
    validate_localization_invariants(english, chinese)

    snapshot.content_en = english.model_dump(mode="json")
    snapshot.content_zh = chinese.model_dump(mode="json")
    snapshot.status = "completed"
    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)
    return snapshot


def _find_snapshot(
    session: Session,
    company: Company,
    filing: Filing,
    model_id: str,
    schema_version: str,
    prompt_version: str,
) -> CompanyIntelligenceSnapshot | None:
    return session.exec(
        select(CompanyIntelligenceSnapshot).where(
            CompanyIntelligenceSnapshot.company_id == company.id,
            CompanyIntelligenceSnapshot.filing_id == filing.id,
            CompanyIntelligenceSnapshot.model_id == model_id,
            CompanyIntelligenceSnapshot.schema_version == schema_version,
            CompanyIntelligenceSnapshot.prompt_version == prompt_version,
        )
    ).first()


def _build_evidence_bundle(
    session: Session,
    company: Company,
    filing: Filing,
) -> EvidenceBundle:
    rows = list(
        session.exec(
            select(FilingSection)
            .where(FilingSection.filing_id == filing.id)
            .order_by(FilingSection.ordinal)
        ).all()
    )
    sections: list[EvidenceSection] = []
    remaining_chars = 300_000
    for row in rows[:20]:
        text = row.text.strip()[: min(120_000, remaining_chars)]
        if len(text) < 20:
            continue
        sections.append(
            EvidenceSection(
                section_id=str(row.id),
                heading=row.heading,
                source_anchor=row.source_anchor,
                source_url=f"{filing.source_url}#{row.source_anchor}",
                text=text,
            )
        )
        remaining_chars -= len(text)
        if remaining_chars < 20:
            break
    if not sections:
        raise DomainError("FILING_EVIDENCE_MISSING", 422)
    return EvidenceBundle(
        symbol=company.symbol,
        company_name=company.name,
        sections=sections,
    )


def _replace_citations(
    session: Session,
    snapshot: CompanyIntelligenceSnapshot,
    filing: Filing,
    evidence: EvidenceBundle,
    citations: list[CitationDraft],
    verdict: str,
) -> None:
    existing = session.exec(
        select(EvidenceCitation).where(
            EvidenceCitation.snapshot_id == snapshot.id
        )
    ).all()
    for citation in existing:
        session.delete(citation)
    sections = {section.section_id: section for section in evidence.sections}
    for citation in citations:
        section = sections[citation.section_id]
        session.add(
            EvidenceCitation(
                snapshot_id=snapshot.id,
                filing_id=filing.id,
                section_label=section.heading,
                source_anchor=section.source_anchor,
                excerpt=citation.excerpt,
                source_url=section.source_url,
                verification_verdict=verdict,
            )
        )
