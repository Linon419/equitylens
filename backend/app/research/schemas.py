from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

Confidence = Literal["High", "Medium", "Low"]
EvidenceCoverage = Literal["complete", "partial", "insufficient_evidence"]
Locale = Literal["en", "zh"]
CATEGORY_FIELDS = (
    "core_businesses",
    "revenue_engines",
    "upstream",
    "company_layer",
    "downstream",
    "competitors",
    "material_dependencies",
)


class IntelligenceClaim(BaseModel):
    claim_id: str = Field(pattern=r"^[a-z]+-[0-9]+$")
    title: str = Field(min_length=1, max_length=120)
    explanation: str = Field(min_length=1, max_length=800)
    confidence: Confidence
    citation_ids: list[str] = Field(min_length=1, max_length=5)
    revenue_share: Decimal | None = Field(default=None, ge=0, le=100)
    revenue_period: str | None = Field(default=None, max_length=32)


class CitationDraft(BaseModel):
    citation_id: str = Field(pattern=r"^citation-[0-9]+$")
    section_id: str = Field(min_length=1, max_length=64)
    excerpt: str = Field(min_length=20, max_length=1000)


class IntelligenceContent(BaseModel):
    core_businesses: list[IntelligenceClaim]
    revenue_engines: list[IntelligenceClaim]
    upstream: list[IntelligenceClaim]
    company_layer: list[IntelligenceClaim]
    downstream: list[IntelligenceClaim]
    competitors: list[IntelligenceClaim]
    material_dependencies: list[IntelligenceClaim]
    citations: list[CitationDraft]

    @model_validator(mode="after")
    def validate_identifiers(self) -> Self:
        claims = self.all_claims()
        claim_ids = [claim.claim_id for claim in claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("duplicate claim IDs")
        citation_ids = [citation.citation_id for citation in self.citations]
        if len(citation_ids) != len(set(citation_ids)):
            raise ValueError("duplicate citation IDs")
        referenced = {
            citation_id for claim in claims for citation_id in claim.citation_ids
        }
        if referenced != set(citation_ids):
            raise ValueError("claim citation membership must be exact")
        return self

    def all_claims(self) -> list[IntelligenceClaim]:
        return [
            claim
            for field in CATEGORY_FIELDS
            for claim in getattr(self, field)
        ]


class IntelligenceDraft(IntelligenceContent):
    pass


class EvidenceSection(BaseModel):
    section_id: str = Field(min_length=1, max_length=64)
    heading: str = Field(min_length=1, max_length=255)
    source_anchor: str = Field(min_length=1, max_length=255)
    source_url: str = Field(min_length=1, max_length=2000)
    text: str = Field(min_length=20, max_length=120_000)


class EvidenceBundle(BaseModel):
    symbol: str = Field(min_length=1, max_length=16)
    company_name: str = Field(min_length=1, max_length=255)
    sections: list[EvidenceSection] = Field(min_length=1, max_length=20)


class VerificationVerdict(BaseModel):
    claim_id: str = Field(pattern=r"^[a-z]+-[0-9]+$")
    supported: bool
    reason: str = Field(min_length=1, max_length=500)


class VerificationResult(BaseModel):
    verdicts: list[VerificationVerdict]

    @model_validator(mode="after")
    def validate_unique_claims(self) -> Self:
        claim_ids = [verdict.claim_id for verdict in self.verdicts]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("duplicate verification claim IDs")
        return self


class VerifiedIntelligence(IntelligenceContent):
    evidence_coverage: EvidenceCoverage
    overall_confidence: Confidence | None


class LocalizedIntelligence(VerifiedIntelligence):
    locale: Locale


class PublicCitation(BaseModel):
    id: str
    filing_type: Literal["10-K"] = "10-K"
    filing_date: date
    section: str
    source_anchor: str
    excerpt: str
    source_url: str


class IntelligenceResponse(BaseModel):
    snapshot_id: str
    symbol: str
    filing_type: Literal["10-K"] = "10-K"
    filing_date: date
    filing_url: str
    evidence_coverage: EvidenceCoverage
    overall_confidence: Confidence | None
    model_id: str
    generated_at: datetime
    content: LocalizedIntelligence
    citations: list[PublicCitation]
