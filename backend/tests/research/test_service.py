import pytest
from sqlmodel import Session, select

from app.core.errors import DomainError
from app.models.company_model import Company
from app.models.research_model import EvidenceCitation, Filing
from app.research.schemas import (
    IntelligenceClaim,
    IntelligenceDraft,
    LocalizedIntelligence,
    VerificationResult,
    VerificationVerdict,
)
from app.research.service import (
    generate_draft,
    localize_snapshot,
    verify_snapshot,
)


class FakeGenerator:
    model_id = "fake-research-model"

    def __init__(self) -> None:
        self.generate_calls = 0
        self.verify_calls = 0
        self.locales: list[str] = []
        self.supported = True

    async def generate(self, bundle) -> IntelligenceDraft:
        self.generate_calls += 1
        section = bundle.sections[0]
        citation = {
            "citation_id": "citation-1",
            "section_id": section.section_id,
            "excerpt": section.text,
        }
        claim = IntelligenceClaim(
            claim_id="business-1",
            title="Devices and services FY2025",
            explanation="Hardware connects a services ecosystem in FY2025.",
            confidence="High",
            citation_ids=["citation-1"],
            revenue_period="FY2025",
        )
        return IntelligenceDraft(
            core_businesses=[claim],
            revenue_engines=[],
            upstream=[],
            company_layer=[],
            downstream=[],
            competitors=[],
            material_dependencies=[],
            citations=[citation],
        )

    async def verify(self, draft) -> VerificationResult:
        self.verify_calls += 1
        return VerificationResult(
            verdicts=[
                VerificationVerdict(
                    claim_id="business-1",
                    supported=self.supported,
                    reason="Exact filing support.",
                )
            ]
        )

    async def localize(self, verified, locale) -> LocalizedIntelligence:
        self.locales.append(locale)
        payload = verified.model_dump()
        if locale == "zh":
            payload["core_businesses"][0]["title"] = "设备与服务 FY2025"
            payload["core_businesses"][0]["explanation"] = (
                "硬件连接 FY2025 服务生态。"
            )
        return LocalizedIntelligence(locale=locale, **payload)


@pytest.mark.asyncio
async def test_generation_verification_and_localization_are_persisted(
    research_session: Session,
    research_records: tuple[Company, Filing],
) -> None:
    company, filing = research_records
    generator = FakeGenerator()

    snapshot = await generate_draft(
        research_session,
        company,
        filing,
        generator,
        schema_version="v1",
        prompt_version="p1",
    )
    snapshot = await verify_snapshot(research_session, snapshot, generator)
    snapshot = await localize_snapshot(research_session, snapshot, generator)

    assert snapshot.status == "completed"
    assert snapshot.content_en["locale"] == "en"
    assert snapshot.content_zh["locale"] == "zh"
    assert snapshot.model_id == "fake-research-model"
    assert generator.locales == ["en", "zh"]
    citations = research_session.exec(select(EvidenceCitation)).all()
    assert len(citations) == 1
    assert citations[0].verification_verdict == "supported"

    reused = await generate_draft(
        research_session,
        company,
        filing,
        generator,
        schema_version="v1",
        prompt_version="p1",
    )
    assert reused.id == snapshot.id
    assert generator.generate_calls == 1


@pytest.mark.asyncio
async def test_verification_fails_when_every_claim_is_unsupported(
    research_session: Session,
    research_records: tuple[Company, Filing],
) -> None:
    company, filing = research_records
    generator = FakeGenerator()
    snapshot = await generate_draft(
        research_session,
        company,
        filing,
        generator,
        schema_version="v1",
        prompt_version="p1",
    )
    generator.supported = False

    with pytest.raises(DomainError) as error:
        await verify_snapshot(research_session, snapshot, generator)

    assert error.value.code == "INSUFFICIENT_EVIDENCE"
    research_session.refresh(snapshot)
    assert snapshot.status == "failed"
