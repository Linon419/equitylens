from datetime import UTC, date, datetime

from sqlmodel import Session, select

from app.core.errors import DomainError
from app.filings.artifacts import compress_filing
from app.filings.mapper import latest_10k
from app.filings.parser import parse_research_sections
from app.filings.schemas import StoredFiling
from app.models.company_model import Company
from app.models.research_model import Filing, FilingArtifact, FilingSection
from app.providers.sec import SecDataProvider


async def download_latest_10k(
    session: Session,
    company: Company,
    provider: SecDataProvider,
    *,
    now: datetime | None = None,
    max_bytes: int = 15 * 1024 * 1024,
) -> StoredFiling:
    current_time = now or datetime.now(UTC)
    submissions = await provider.get_submissions(company.cik)
    reference = latest_10k(company.cik, submissions)
    existing = _find_filing(session, company, reference.accession_number)
    if existing is not None:
        stored = _load_complete_filing(session, existing)
        if stored is not None:
            return stored

    content = await provider.download_filing(reference)
    _validate_html(content.content_type, content.body)
    compressed = compress_filing(content.body, max_bytes=max_bytes)
    sections = parse_research_sections(content.body)

    try:
        filing = existing or Filing(
            company_id=company.id,
            accession_number=reference.accession_number,
            form=reference.form,
            fiscal_period=f"FY{reference.report_date[:4]}",
            filed_at=reference.filed_at.date(),
            report_date=date.fromisoformat(reference.report_date),
            primary_document=reference.primary_document,
            source_url=reference.source_url,
            retrieved_at=current_time,
        )
        filing.content_hash = compressed.sha256
        filing.retrieved_at = current_time
        session.add(filing)
        session.flush()

        artifact = session.get(FilingArtifact, filing.id)
        if artifact is None:
            artifact = FilingArtifact(
                filing_id=filing.id,
                content_type=content.content_type,
                compressed_body=compressed.compressed_body,
                compressed_size=compressed.compressed_size,
                uncompressed_size=compressed.uncompressed_size,
                sha256=compressed.sha256,
            )
        else:
            artifact.content_type = content.content_type
            artifact.compressed_body = compressed.compressed_body
            artifact.compressed_size = compressed.compressed_size
            artifact.uncompressed_size = compressed.uncompressed_size
            artifact.sha256 = compressed.sha256
        session.add(artifact)

        for old_section in _filing_sections(session, filing):
            session.delete(old_section)
        for section in sections:
            session.add(
                FilingSection(
                    filing_id=filing.id,
                    heading=section.heading,
                    source_anchor=section.source_anchor,
                    ordinal=section.ordinal,
                    text=section.text,
                )
            )
        session.commit()
    except Exception:
        session.rollback()
        raise

    session.refresh(filing)
    stored_artifact = session.get(FilingArtifact, filing.id)
    if stored_artifact is None:
        raise DomainError("FILING_ARTIFACT_MISSING", 500)
    return StoredFiling(
        filing=filing,
        artifact=stored_artifact,
        sections=tuple(_filing_sections(session, filing)),
    )


def _find_filing(
    session: Session,
    company: Company,
    accession_number: str,
) -> Filing | None:
    return session.exec(
        select(Filing).where(
            Filing.company_id == company.id,
            Filing.accession_number == accession_number,
        )
    ).first()


def _load_complete_filing(
    session: Session,
    filing: Filing,
) -> StoredFiling | None:
    artifact = session.get(FilingArtifact, filing.id)
    if (
        artifact is None
        or filing.content_hash is None
        or artifact.sha256 != filing.content_hash
    ):
        return None
    return StoredFiling(
        filing=filing,
        artifact=artifact,
        sections=tuple(_filing_sections(session, filing)),
    )


def _filing_sections(
    session: Session,
    filing: Filing,
) -> list[FilingSection]:
    return list(
        session.exec(
            select(FilingSection)
            .where(FilingSection.filing_id == filing.id)
            .order_by(FilingSection.ordinal)
        ).all()
    )


def _validate_html(content_type: str, body: bytes) -> None:
    signature = body.lstrip()[:32].lower()
    content_type_is_html = "html" in content_type.lower()
    body_is_html = signature.startswith((b"<!doctype html", b"<html"))
    if not content_type_is_html and not body_is_html:
        raise DomainError("FILING_CONTENT_INVALID", 415)
