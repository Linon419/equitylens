from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

EvidenceAttribute = str | int | float | bool | None
EvidenceCoverage = Literal["complete", "partial", "insufficient"]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EvidenceCandidate(_StrictModel):
    evidence_id: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
    ]
    source_kind: Literal["filing", "financial", "intelligence", "graph", "web"]
    source_id: Annotated[str, StringConstraints(max_length=255)] | None
    title: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
    ]
    source_url: str
    source_anchor: Annotated[str, StringConstraints(max_length=255)] | None
    excerpt: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=1_000),
    ]
    published_at: datetime | None
    retrieved_at: datetime
    source_tier: Literal["primary", "trusted_secondary", "derived"]
    verification: Literal["verified", "supporting"]
    attributes: dict[str, EvidenceAttribute] = Field(default_factory=dict)

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str) -> str:
        if not value.startswith("https://") or len(value) > 2_000:
            raise ValueError("evidence source URL must use HTTPS")
        return value


class ApprovedEvidenceRecord(_StrictModel):
    company_id: int | None = Field(default=None, ge=1)
    candidate: EvidenceCandidate
    source_text: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=200_000),
    ]


class AnswerEvidencePack(_StrictModel):
    company_id: int = Field(ge=1)
    company_name: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
    ]
    symbol: Annotated[
        str,
        StringConstraints(pattern=r"^[A-Z][A-Z0-9.-]{0,15}$"),
    ]
    records: list[ApprovedEvidenceRecord] = Field(default_factory=list, max_length=64)
    evidence_gaps: list[
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
        ]
    ] = Field(default_factory=list, max_length=24)
    web_search_used: bool

    @field_validator("records")
    @classmethod
    def validate_unique_evidence(
        cls,
        value: list[ApprovedEvidenceRecord],
    ) -> list[ApprovedEvidenceRecord]:
        evidence_ids = [record.candidate.evidence_id for record in value]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("duplicate approved evidence ID")
        return value


class AnswerPoint(_StrictModel):
    text: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=4_000),
    ]
    citation_ids: list[
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
        ]
    ] = Field(default_factory=list, max_length=8)
    inference: bool = False

    @field_validator("citation_ids")
    @classmethod
    def validate_unique_citations(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("duplicate citation ID in answer point")
        return value


class ResearchAnswerPlan(_StrictModel):
    direct_conclusion: AnswerPoint
    key_evidence: list[AnswerPoint] = Field(min_length=1, max_length=8)
    risks_and_uncertainties: list[AnswerPoint] = Field(
        default_factory=list,
        max_length=6,
    )
    sources: list[
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
        ]
    ] = Field(default_factory=list, max_length=24)
    evidence_coverage: EvidenceCoverage
    web_search_used: bool

    @field_validator("sources")
    @classmethod
    def validate_unique_sources(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("duplicate answer source")
        return value


class StoredResearchAnswer(_StrictModel):
    response_kind: Literal["research"] = "research"
    is_follow_up: bool
    resolved_question: Annotated[
        str,
        StringConstraints(strip_whitespace=True, max_length=2_000),
    ]
    answer: ResearchAnswerPlan


class StoredPlainAnswer(_StrictModel):
    response_kind: Literal["conversation", "clarification"]
    is_follow_up: bool
    content: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=4_000),
    ]


StoredAgentAnswer = Annotated[
    StoredResearchAnswer | StoredPlainAnswer,
    Field(discriminator="response_kind"),
]


def stored_response_kind(
    payload: dict | None,
) -> Literal["conversation", "clarification", "research"] | None:
    if payload is None:
        return None
    kind = payload.get("response_kind")
    if kind in {"conversation", "clarification", "research"}:
        return kind
    return "research"


class CitationSnapshot(_StrictModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    evidence_id: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    ordinal: int = Field(ge=0)
    source_kind: Literal["filing", "financial", "intelligence", "graph", "web"]
    source_id: Annotated[str, StringConstraints(max_length=255)] | None
    title: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    source_url: str
    source_anchor: Annotated[str, StringConstraints(max_length=255)] | None
    excerpt: Annotated[str, StringConstraints(min_length=1, max_length=1_000)]
    published_at: datetime | None
    retrieved_at: datetime
    source_tier: Literal["primary", "trusted_secondary", "derived"]
    verification: Literal["verified", "supporting"]

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str) -> str:
        if not value.startswith("https://") or len(value) > 2_000:
            raise ValueError("citation source URL must use HTTPS")
        return value
