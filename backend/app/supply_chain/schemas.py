from datetime import date, datetime
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.jobs.schemas import JobPublic
from app.quota.schemas import QuotaStatus

NodeKind = Literal["company", "business", "product", "category"]
NodeLayer = Literal["upstream", "core", "downstream"]
EdgeType = Literal[
    "supplies",
    "manufactures_for",
    "distributes_for",
    "sells_to",
    "licenses_to",
    "platform_for",
    "component_of",
    "serves_market",
]
EvidenceStatus = Literal["verified", "potential", "internal"]
PublicEvidenceStatus = Literal["verified", "potential"]
VerificationVerdict = Literal["verified", "potential", "rejected", "conflicted"]
SourceType = Literal[
    "sec_filing",
    "annual_report",
    "ir_page",
    "official_press_release",
]
SupportRole = Literal["primary", "corroborating"]
ConfidenceLabel = Literal["High", "Medium", "Low"]
AcceptedGraphStatus = Literal["completed", "insufficient_evidence"]
EvidenceCoverage = Literal["complete", "partial", "insufficient_evidence"]

StableKey = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=255),
]
ShortText = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=255),
]
Description = Annotated[
    str,
    StringConstraints(
        strict=True, strip_whitespace=True, min_length=1, max_length=2000
    ),
]
Score = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]
PositiveId = Annotated[int, Field(strict=True, gt=0)]
Rank = Annotated[int, Field(strict=True, ge=0)]
Symbol = Annotated[
    str,
    StringConstraints(
        strict=True,
        min_length=1,
        max_length=16,
        pattern=r"^[A-Z0-9.-]+$",
    ),
]
Cik = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^[0-9]{10}$"),
]
ModelId = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=128),
]


def _validate_canonical_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise ValueError("canonical URL is malformed") from error
    if parsed.scheme != "https" or parsed.hostname is None:
        raise ValueError("canonical URL requires HTTPS and a hostname")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("canonical URL cannot contain user information")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("canonical URL port is invalid")
    return value


CanonicalUrl = Annotated[
    str,
    StringConstraints(strict=True, min_length=10, max_length=2000),
    AfterValidator(_validate_canonical_url),
]


def _require_nonblank_exact_text(value: str) -> str:
    if not value.strip():
        raise ValueError("must contain non-whitespace characters")
    return value


ExactEvidenceText = Annotated[
    str,
    StringConstraints(strict=True, min_length=20, max_length=2000),
    AfterValidator(_require_nonblank_exact_text),
]
ExactBodyText = Annotated[
    str,
    StringConstraints(strict=True, min_length=20, max_length=500_000),
    AfterValidator(_require_nonblank_exact_text),
]


class StrictValueModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FrozenValueModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CompanyIdentity(FrozenValueModel):
    company_id: PositiveId
    symbol: Symbol
    cik: Cik
    legal_name: ShortText
    exchange: ShortText | None = None
    official_hosts: tuple[
        Annotated[
            str,
            StringConstraints(
                strict=True,
                strip_whitespace=True,
                to_lower=True,
                min_length=3,
                max_length=253,
                pattern=r"^[a-z0-9.-]+$",
            ),
        ],
        ...,
    ] = Field(min_length=1, max_length=12)

    @field_validator("official_hosts")
    @classmethod
    def validate_unique_hosts(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("duplicate official hosts")
        return value


class OfficialSourceMetadata(FrozenValueModel):
    source_id: StableKey
    source_key: StableKey
    source_type: SourceType
    publisher: ShortText
    title: Annotated[
        str,
        StringConstraints(
            strict=True,
            strip_whitespace=True,
            min_length=1,
            max_length=500,
        ),
    ]
    canonical_url: CanonicalUrl
    published_at: date | None = None


class OfficialSourceDocument(OfficialSourceMetadata):
    content_hash: Annotated[
        str,
        StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$"),
    ]
    artifact_key: Annotated[
        str,
        StringConstraints(
            strict=True,
            strip_whitespace=True,
            min_length=1,
            max_length=1024,
        ),
    ]
    content_type: Annotated[
        str,
        StringConstraints(
            strict=True,
            strip_whitespace=True,
            min_length=3,
            max_length=120,
        ),
    ]
    body_text: ExactBodyText


class SourcePlan(StrictValueModel):
    selected_source_ids: list[StableKey] = Field(min_length=1, max_length=24)
    rationale_en: Description
    relevant_sections: list[ShortText] = Field(min_length=1, max_length=24)

    @field_validator("selected_source_ids")
    @classmethod
    def validate_unique_source_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("duplicate selected source IDs")
        return value


class EvidenceReference(FrozenValueModel):
    source_key: StableKey
    excerpt: ExactEvidenceText
    locator: Annotated[
        str,
        StringConstraints(
            strict=True,
            strip_whitespace=True,
            min_length=1,
            max_length=240,
        ),
    ]
    support_role: SupportRole = "primary"
    confidence: Score = 1.0


class EntityCandidate(FrozenValueModel):
    node_key: StableKey
    label_en: ShortText
    symbol: Symbol | None = None
    cik: Cik | None = None


class ResolvedEntity(FrozenValueModel):
    node_key: StableKey
    company_id: PositiveId | None = None
    symbol: Symbol | None = None
    cik: Cik | None = None
    legal_name: ShortText | None = None
    resolution_status: Literal["resolved", "unresolved", "ambiguous"]
    confidence: Score


class GraphNodeDraft(StrictValueModel):
    node_key: StableKey
    kind: NodeKind
    layer: NodeLayer
    label_en: ShortText
    description_en: Description
    company_id: PositiveId | None = None
    symbol: Symbol | None = None
    cik: Cik | None = None
    importance: Score
    confidence: Score
    rank: Rank = 0


class GraphEdgeDraft(StrictValueModel):
    edge_key: StableKey
    source_node_key: StableKey
    target_node_key: StableKey
    relationship_type: EdgeType
    evidence_status: EvidenceStatus
    confidence: Score
    importance: Score
    explanation_en: Description
    evidence_refs: list[EvidenceReference] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        if self.evidence_status in {"verified", "potential"} and not self.evidence_refs:
            raise ValueError(
                "verified or potential edge requires an evidence reference"
            )
        identities = [
            (
                reference.source_key,
                reference.excerpt,
                reference.locator,
                reference.support_role,
            )
            for reference in self.evidence_refs
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("duplicate evidence references")
        return self


class GraphDraft(StrictValueModel):
    focus_node_key: StableKey
    thesis_en: Description
    nodes: list[GraphNodeDraft] = Field(min_length=1, max_length=40)
    edges: list[GraphEdgeDraft] = Field(default_factory=list, max_length=120)

    @model_validator(mode="after")
    def validate_graph(self) -> Self:
        node_keys = [node.node_key for node in self.nodes]
        if len(node_keys) != len(set(node_keys)):
            raise ValueError("duplicate node keys")
        if node_keys.count(self.focus_node_key) != 1:
            raise ValueError("focus_node_key must match exactly one node")
        edge_keys = [edge.edge_key for edge in self.edges]
        if len(edge_keys) != len(set(edge_keys)):
            raise ValueError("duplicate edge keys")
        known_nodes = set(node_keys)
        for edge in self.edges:
            if edge.source_node_key == edge.target_node_key:
                raise ValueError(f"self-edge is forbidden: {edge.edge_key}")
            if {edge.source_node_key, edge.target_node_key} - known_nodes:
                raise ValueError(f"edge has unknown endpoint: {edge.edge_key}")
        return self


class EdgeVerification(StrictValueModel):
    edge_key: StableKey
    verdict: VerificationVerdict
    confidence: Score
    reason_en: Description
    evidence_refs: list[EvidenceReference] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def validate_verdict_evidence(self) -> Self:
        if self.verdict in {"verified", "potential"} and not self.evidence_refs:
            raise ValueError(
                "verified or potential verdict requires an evidence reference"
            )
        return self


class GraphVerification(StrictValueModel):
    edge_verifications: list[EdgeVerification] = Field(
        default_factory=list, max_length=120
    )

    @model_validator(mode="after")
    def validate_unique_edges(self) -> Self:
        edge_keys = [decision.edge_key for decision in self.edge_verifications]
        if len(edge_keys) != len(set(edge_keys)):
            raise ValueError("duplicate edge verification")
        return self


class EdgeRejection(FrozenValueModel):
    edge_key: StableKey
    verdict: Literal["rejected", "conflicted"]
    reason_en: Description
    evidence_refs: tuple[EvidenceReference, ...] = Field(
        default_factory=tuple, max_length=12
    )


class AcceptedGraph(StrictValueModel):
    status: AcceptedGraphStatus
    focus_node_key: StableKey
    thesis_en: Description
    accepted_nodes: list[GraphNodeDraft] = Field(min_length=1, max_length=40)
    public_edges: list[GraphEdgeDraft] = Field(default_factory=list, max_length=120)
    potential_edges: list[GraphEdgeDraft] = Field(default_factory=list, max_length=120)
    internal_edges: list[GraphEdgeDraft] = Field(default_factory=list, max_length=120)
    rejected_edges: list[EdgeRejection] = Field(default_factory=list, max_length=120)
    sources: list[OfficialSourceMetadata] = Field(default_factory=list, max_length=24)
    evidence_coverage: Score
    overall_confidence: ConfidenceLabel | None = None
    reason_codes: list[StableKey] = Field(default_factory=list, max_length=24)

    @model_validator(mode="after")
    def validate_accepted_graph(self) -> Self:
        node_keys = [node.node_key for node in self.accepted_nodes]
        if len(node_keys) != len(set(node_keys)):
            raise ValueError("duplicate accepted node keys")
        if node_keys.count(self.focus_node_key) != 1:
            raise ValueError("focus_node_key must match exactly one accepted node")
        edge_groups = (
            (self.public_edges, "verified"),
            (self.potential_edges, "potential"),
            (self.internal_edges, "internal"),
        )
        known_nodes = set(node_keys)
        all_edge_keys: list[str] = []
        for edges, expected_status in edge_groups:
            for edge in edges:
                if edge.evidence_status != expected_status:
                    raise ValueError(f"{expected_status} edge list has wrong status")
                if {edge.source_node_key, edge.target_node_key} - known_nodes:
                    raise ValueError(
                        f"accepted edge has unknown endpoint: {edge.edge_key}"
                    )
                all_edge_keys.append(edge.edge_key)
        if len(all_edge_keys) != len(set(all_edge_keys)):
            raise ValueError("duplicate accepted edge keys")
        source_keys = [source.source_key for source in self.sources]
        if len(source_keys) != len(set(source_keys)):
            raise ValueError("duplicate accepted source keys")
        return self


class LocalizedGraphNode(StrictValueModel):
    node_key: StableKey
    kind: NodeKind
    layer: NodeLayer
    label_zh: ShortText
    description_zh: Description
    company_id: PositiveId | None = None
    symbol: Symbol | None = None
    cik: Cik | None = None
    importance: Score
    confidence: Score
    rank: Rank = 0


class LocalizedGraphEdge(StrictValueModel):
    edge_key: StableKey
    source_node_key: StableKey
    target_node_key: StableKey
    relationship_type: EdgeType
    evidence_status: EvidenceStatus
    confidence: Score
    importance: Score
    explanation_zh: Description
    evidence_refs: list[EvidenceReference] = Field(default_factory=list, max_length=12)


class GraphLocalization(StrictValueModel):
    locale: Literal["zh"] = "zh"
    focus_node_key: StableKey
    thesis_zh: Description
    nodes: list[LocalizedGraphNode] = Field(min_length=1, max_length=40)
    public_edges: list[LocalizedGraphEdge] = Field(default_factory=list, max_length=120)
    potential_edges: list[LocalizedGraphEdge] = Field(
        default_factory=list, max_length=120
    )
    internal_edges: list[LocalizedGraphEdge] = Field(
        default_factory=list, max_length=120
    )


class PublicGraphSnapshotSummary(StrictValueModel):
    id: UUID
    status: AcceptedGraphStatus
    symbol: Symbol
    model_id: ModelId
    focus_node_key: StableKey
    thesis: Description
    evidence_coverage: EvidenceCoverage
    overall_confidence: ConfidenceLabel | None
    node_count: Annotated[int, Field(strict=True, ge=0, le=40)]
    edge_count: Annotated[int, Field(strict=True, ge=0, le=240)]
    generated_at: datetime


class PublicGraphNode(StrictValueModel):
    id: UUID
    node_key: StableKey
    kind: NodeKind
    layer: NodeLayer
    label: ShortText
    description: Description
    symbol: Symbol | None = None
    cik: Cik | None = None
    importance: Score
    confidence: ConfidenceLabel
    rank: Rank


class PublicGraphCitation(StrictValueModel):
    id: UUID
    source_id: UUID
    source_key: StableKey
    excerpt: ExactEvidenceText
    locator: Annotated[
        str,
        StringConstraints(
            strict=True,
            strip_whitespace=True,
            min_length=1,
            max_length=240,
        ),
    ]
    support_role: SupportRole
    confidence: Score


class PublicGraphEdge(StrictValueModel):
    id: UUID
    edge_key: StableKey
    source: UUID
    target: UUID
    relationship_type: EdgeType
    evidence_status: PublicEvidenceStatus
    confidence: ConfidenceLabel
    importance: Score
    explanation: Description
    citations: list[PublicGraphCitation] = Field(min_length=1, max_length=12)


class PublicGraphSource(OfficialSourceMetadata):
    id: UUID


class PublicSupplyChainGraph(StrictValueModel):
    snapshot: PublicGraphSnapshotSummary
    nodes: list[PublicGraphNode] = Field(max_length=40)
    edges: list[PublicGraphEdge] = Field(max_length=240)
    sources: list[PublicGraphSource] = Field(max_length=24)
    refresh_job: JobPublic | None = None
    quota: QuotaStatus


class GraphRefreshRequest(StrictValueModel):
    force_refresh: Annotated[bool, Field(strict=True)] = False


class GraphRefreshResponse(StrictValueModel):
    status: Literal["accepted", "active_job", "reused_snapshot"]
    job: JobPublic | None = None
    job_id: UUID | None = None
    snapshot_id: UUID | None = None
    quota: QuotaStatus

    @model_validator(mode="after")
    def validate_status_reference(self) -> Self:
        if (
            self.status in {"accepted", "active_job"}
            and self.job is None
            and self.job_id is None
        ):
            raise ValueError(f"{self.status} requires job or job_id")
        if self.status == "reused_snapshot" and self.snapshot_id is None:
            raise ValueError("reused_snapshot requires snapshot_id")
        return self
