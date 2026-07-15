import re
import unicodedata
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

Locale = Literal["en-US", "zh-CN"]
EvidenceCoverage = Literal["complete", "partial", "insufficient"]
ConversationTitle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]
MessageText = Annotated[str, StringConstraints(min_length=1, max_length=2_000)]
MetricKey = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$"),
]
PeriodKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=32),
]
ClaimKey = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z]+-[0-9]+$"),
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QueryRewrite(StrictModel):
    filing_query_en: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
    ]
    display_query: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
    ]
    current_intent: bool


class MarketMetricContext(StrictModel):
    kind: Literal["market_metric"] = "market_metric"
    metric_key: Literal[
        "price",
        "market_cap",
        "trailing_eps",
        "trailing_pe",
        "forward_pe",
    ]
    observed_at: datetime | None = None


class FinancialMetricContext(StrictModel):
    kind: Literal["financial_metric"] = "financial_metric"
    metric_key: MetricKey
    period_key: PeriodKey


class BusinessClaimContext(StrictModel):
    kind: Literal["business_claim"] = "business_claim"
    id: ClaimKey
    snapshot_id: UUID


class SupplyChainNodeContext(StrictModel):
    kind: Literal["supply_chain_node"] = "supply_chain_node"
    id: UUID
    snapshot_id: UUID


class SupplyChainEdgeContext(StrictModel):
    kind: Literal["supply_chain_edge"] = "supply_chain_edge"
    id: UUID
    snapshot_id: UUID


ContextSelection = Annotated[
    MarketMetricContext
    | FinancialMetricContext
    | BusinessClaimContext
    | SupplyChainNodeContext
    | SupplyChainEdgeContext,
    Field(discriminator="kind"),
]


class ConversationCreate(StrictModel):
    locale: Locale
    title: ConversationTitle | None = None


class ConversationPatch(StrictModel):
    title: ConversationTitle


class ConversationPublic(StrictModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    company_id: int
    title: str
    locale: Locale
    expires_at: datetime | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MessageCreate(StrictModel):
    client_request_id: UUID
    content: MessageText
    locale: Locale
    context: list[ContextSelection] = Field(default_factory=list, max_length=12)

    @field_validator("content", mode="before")
    @classmethod
    def normalize_content(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = unicodedata.normalize("NFKC", value)
        return re.sub(r"\s+", " ", normalized).strip()


class CitationPublic(StrictModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    ordinal: int
    source_kind: Literal["filing", "financial", "intelligence", "graph", "web"]
    source_id: str | None
    title: str
    source_url: str
    source_anchor: str | None
    excerpt: str
    published_at: datetime | None
    retrieved_at: datetime
    source_tier: Literal["primary", "trusted_secondary", "derived"]
    verification: Literal["verified", "supporting"]


EvidenceAttribute = str | int | float | bool | None


class EvidenceCandidate(StrictModel):
    evidence_id: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
    ]
    source_kind: Literal["filing", "financial", "intelligence", "graph", "web"]
    source_id: str | None
    title: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
    ]
    source_url: str
    source_anchor: str | None
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


class StructuredContextItem(StrictModel):
    kind: Literal[
        "market_metric",
        "financial_metric",
        "business_claim",
        "supply_chain_node",
        "supply_chain_edge",
    ]
    source_id: str
    label: str
    description: str
    citation: EvidenceCandidate


class EvidenceGap(StrictModel):
    resource: Literal[
        "market",
        "financials",
        "intelligence",
        "filing_text",
        "filing_index",
        "supply_chain_graph",
        "web_recency",
    ]
    code: str
    action: Literal[
        "company_analysis",
        "filing_index",
        "supply_chain_graph",
    ] | None = None


class MessagePublic(StrictModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    conversation_id: UUID
    reply_to_message_id: UUID | None
    role: Literal["user", "assistant"]
    state: Literal["pending", "planning", "completed", "failed"]
    content: str
    locale: Locale
    evidence_coverage: EvidenceCoverage | None
    error_code: str | None
    attempt_count: int
    created_at: datetime
    completed_at: datetime | None
    citations: list[CitationPublic] = Field(default_factory=list)


class MessagePage(StrictModel):
    items: list[MessagePublic]
    next_cursor: str | None


class ReadinessResource(StrictModel):
    state: Literal["ready", "missing", "running", "failed"]
    action: Literal["company_analysis", "filing_index", "supply_chain_graph"] | None


class ChatReadiness(StrictModel):
    company_symbol: str
    intelligence: ReadinessResource
    filing_text: ReadinessResource
    filing_index: ReadinessResource
    supply_chain_graph: ReadinessResource
    web_recency: ReadinessResource


class StructuredContextPack(StrictModel):
    items: list[StructuredContextItem]
    evidence: list[EvidenceCandidate]
    readiness: ChatReadiness
    gaps: list[EvidenceGap]


class ChatQuotaStatus(StrictModel):
    limit: int
    used: int
    remaining: int
    resets_at: datetime


class AcceptedEvent(StrictModel):
    user_message_id: UUID
    assistant_message_id: UUID
    conversation_id: UUID
    quota: ChatQuotaStatus


class StageEvent(StrictModel):
    stage: Literal["retrieval", "web", "compose", "verify"]
    status_key: str


class SectionEvent(StrictModel):
    section: Literal[
        "direct_conclusion",
        "key_evidence",
        "risks_and_uncertainties",
        "sources",
    ]
    delta: str


class CompleteEvent(StrictModel):
    message: MessagePublic
    citations: list[CitationPublic]
    evidence_coverage: EvidenceCoverage
    quota: ChatQuotaStatus


class ErrorEvent(StrictModel):
    code: str
    retryable: bool
    assistant_message_id: UUID
    quota: ChatQuotaStatus
