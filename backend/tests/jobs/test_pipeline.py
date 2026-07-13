import json
from pathlib import Path

import pytest
from sqlmodel import Session

from app.jobs.pipeline import CompanyIntelligencePipeline
from app.models.company_model import Company
from app.models.job_model import IngestionJob
from app.providers.sec import FilingContent
from app.research.schemas import (
    IntelligenceClaim,
    IntelligenceDraft,
    LocalizedIntelligence,
    VerificationResult,
    VerificationVerdict,
)

SEC_FIXTURES = Path(__file__).parents[1] / "fixtures" / "sec"


class PipelineSecProvider:
    def __init__(self) -> None:
        self.download_calls = 0

    async def get_submissions(self, cik: str) -> dict:
        return json.loads((SEC_FIXTURES / "aapl_submissions.json").read_text())

    async def download_filing(self, filing) -> FilingContent:
        self.download_calls += 1
        return FilingContent(
            body=(SEC_FIXTURES / "aapl_10k_excerpt.html").read_bytes(),
            content_type="text/html",
            source_url=filing.source_url,
        )


class PipelineGenerator:
    model_id = "model-1"

    def __init__(self) -> None:
        self.generate_calls = 0
        self.verify_calls = 0
        self.locales: list[str] = []

    async def generate(self, bundle) -> IntelligenceDraft:
        self.generate_calls += 1
        section = bundle.sections[0]
        return IntelligenceDraft(
            core_businesses=[
                IntelligenceClaim(
                    claim_id="business-1",
                    title="Devices and services",
                    explanation="Products connect a services ecosystem.",
                    confidence="High",
                    citation_ids=["citation-1"],
                )
            ],
            revenue_engines=[],
            upstream=[],
            company_layer=[],
            downstream=[],
            competitors=[],
            material_dependencies=[],
            citations=[
                {
                    "citation_id": "citation-1",
                    "section_id": section.section_id,
                    "excerpt": section.text[:1000],
                }
            ],
        )

    async def verify(self, draft) -> VerificationResult:
        self.verify_calls += 1
        return VerificationResult(
            verdicts=[
                VerificationVerdict(
                    claim_id="business-1",
                    supported=True,
                    reason="Supported by the filing.",
                )
            ]
        )

    async def localize(self, verified, locale) -> LocalizedIntelligence:
        self.locales.append(locale)
        return LocalizedIntelligence(locale=locale, **verified.model_dump())


@pytest.mark.asyncio
async def test_pipeline_runs_in_order_and_reuses_completed_steps(
    job_session: Session,
    job_company: Company,
) -> None:
    job = IngestionJob(
        company_id=job_company.id,
        requested_by_type="guest",
        requested_by_hash="guest-hash",
        deduplication_key="pipeline-test",
        state="queued",
        current_step="queued",
    )
    job_session.add(job)
    job_session.commit()
    job_session.refresh(job)
    sec = PipelineSecProvider()
    generator = PipelineGenerator()
    pipeline = CompanyIntelligencePipeline(
        job_session,
        sec,
        generator,
        schema_version="v1",
        prompt_version="p1",
    )

    await pipeline.download(job.id)
    await pipeline.download(job.id)
    await pipeline.parse(job.id)
    await pipeline.analyze(job.id)
    await pipeline.verify(job.id)
    await pipeline.localize(job.id)

    job_session.refresh(job)
    assert job.state == "completed"
    assert job.snapshot_id is not None
    assert sec.download_calls == 1
    assert generator.generate_calls == 1
    assert generator.verify_calls == 1
    assert generator.locales == ["en", "zh"]
