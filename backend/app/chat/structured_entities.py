from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from app.chat.schemas import (
    BusinessClaimContext,
    EvidenceCandidate,
    StructuredContextItem,
    SupplyChainEdgeContext,
    SupplyChainNodeContext,
)
from app.chat.structured_repository import (
    GraphCitationRecord,
    SqlStructuredContextRepository,
)
from app.core.errors import DomainError
from app.models.company_model import Company
from app.models.research_model import CompanyIntelligenceSnapshot, EvidenceCitation
from app.models.supply_chain_model import SupplyChainGraphSnapshot


class EntityContextResolver:
    def __init__(
        self,
        repository: SqlStructuredContextRepository,
        *,
        now: datetime,
    ) -> None:
        self._repository = repository
        self._now = now

    def business_item(
        self,
        company: Company,
        selection: BusinessClaimContext,
        locale: str,
        snapshot: CompanyIntelligenceSnapshot | None,
    ) -> StructuredContextItem:
        if snapshot is None or snapshot.id != selection.snapshot_id:
            raise DomainError("CHAT_CONTEXT_INVALID", 422)
        payload = snapshot.content_en if locale == "en-US" else snapshot.content_zh
        claim, category = _find_claim(payload, selection.id)
        draft = _claim_citation(payload, claim)
        stored = _stored_citation(
            self._repository.intelligence_citations(snapshot.id),
            draft,
        )
        filing = self._repository.filing(stored.filing_id)
        if filing is None or filing.company_id != company.id:
            raise DomainError("CHAT_CONTEXT_INVALID", 422)
        citation = EvidenceCandidate(
            evidence_id=f"intelligence:{snapshot.id}:{selection.id}",
            source_kind="intelligence",
            source_id=f"{snapshot.id}:{selection.id}",
            title=str(claim["title"]),
            source_url=_with_anchor(stored.source_url, stored.source_anchor),
            source_anchor=stored.source_anchor,
            excerpt=stored.excerpt,
            published_at=_date_time(filing.filed_at),
            retrieved_at=self._now,
            source_tier="derived",
            verification="verified",
            attributes={
                "claim_id": selection.id,
                "category": category,
                "confidence": str(claim["confidence"]),
            },
        )
        return StructuredContextItem(
            kind=selection.kind,
            source_id=f"{snapshot.id}:{selection.id}",
            label=str(claim["title"]),
            description=str(claim["explanation"]),
            citation=citation,
        )

    def node_item(
        self,
        selection: SupplyChainNodeContext,
        locale: str,
        snapshot: SupplyChainGraphSnapshot | None,
    ) -> StructuredContextItem:
        _require_graph_snapshot(snapshot, selection.snapshot_id)
        node = self._repository.graph_node(selection.snapshot_id, selection.id)
        record = self._repository.graph_citation_for_node(
            selection.snapshot_id,
            selection.id,
        )
        if node is None or record is None:
            raise DomainError("CHAT_CONTEXT_INVALID", 422)
        return StructuredContextItem(
            kind=selection.kind,
            source_id=str(node.id),
            label=node.label_en if locale == "en-US" else node.label_zh,
            description=(
                node.description_en if locale == "en-US" else node.description_zh
            ),
            citation=self._graph_candidate(selection.id, record),
        )

    def edge_item(
        self,
        selection: SupplyChainEdgeContext,
        locale: str,
        snapshot: SupplyChainGraphSnapshot | None,
    ) -> StructuredContextItem:
        _require_graph_snapshot(snapshot, selection.snapshot_id)
        edge = self._repository.graph_edge(selection.snapshot_id, selection.id)
        record = self._repository.graph_citation_for_edge(
            selection.snapshot_id,
            selection.id,
        )
        if edge is None or record is None:
            raise DomainError("CHAT_CONTEXT_INVALID", 422)
        explanation = (
            edge.explanation_en if locale == "en-US" else edge.explanation_zh
        )
        return StructuredContextItem(
            kind=selection.kind,
            source_id=str(edge.id),
            label=explanation,
            description=edge.relationship_type,
            citation=self._graph_candidate(selection.id, record),
        )

    def _graph_candidate(
        self,
        entity_id: UUID,
        record: GraphCitationRecord,
    ) -> EvidenceCandidate:
        published = (
            _date_time(record.source.published_at)
            if record.source.published_at is not None
            else None
        )
        return EvidenceCandidate(
            evidence_id=(
                f"graph:{record.edge.snapshot_id}:{entity_id}:"
                f"{record.citation.id}"
            ),
            source_kind="graph",
            source_id=str(entity_id),
            title=record.source.title[:255],
            source_url=record.source.canonical_url,
            source_anchor=record.citation.source_anchor,
            excerpt=record.citation.excerpt[:1_000],
            published_at=published,
            retrieved_at=self._now,
            source_tier="primary",
            verification=(
                "verified"
                if record.edge.evidence_status == "verified"
                else "supporting"
            ),
            attributes={
                "relationship_type": record.edge.relationship_type,
                "confidence": record.edge.confidence,
            },
        )


def _find_claim(
    payload: dict[str, Any] | None,
    claim_id: str,
) -> tuple[dict[str, Any], str]:
    if not isinstance(payload, dict):
        raise DomainError("CHAT_CONTEXT_INVALID", 422)
    for category in (
        "core_businesses",
        "revenue_engines",
        "upstream",
        "company_layer",
        "downstream",
        "competitors",
        "material_dependencies",
    ):
        for claim in payload.get(category, []):
            if claim.get("claim_id") == claim_id:
                return claim, category
    raise DomainError("CHAT_CONTEXT_INVALID", 422)


def _claim_citation(
    payload: dict[str, Any] | None,
    claim: dict[str, Any],
) -> dict[str, Any]:
    if payload is None:
        raise DomainError("CHAT_CONTEXT_INVALID", 422)
    citation_ids = claim.get("citation_ids", [])
    citations = {
        item.get("citation_id"): item for item in payload.get("citations", [])
    }
    if not citation_ids or citation_ids[0] not in citations:
        raise DomainError("CHAT_CONTEXT_INVALID", 422)
    return citations[citation_ids[0]]


def _stored_citation(
    rows: list[EvidenceCitation],
    draft: dict[str, Any],
) -> EvidenceCitation:
    row = next(
        (item for item in rows if item.excerpt == draft.get("excerpt")),
        None,
    )
    if row is None:
        raise DomainError("CHAT_CONTEXT_INVALID", 422)
    return row


def _require_graph_snapshot(
    snapshot: SupplyChainGraphSnapshot | None,
    requested_id: UUID,
) -> None:
    if snapshot is None or snapshot.id != requested_id:
        raise DomainError("CHAT_CONTEXT_INVALID", 422)


def _with_anchor(url: str, anchor: str) -> str:
    return f"{url.split('#', 1)[0]}#{anchor}"


def _date_time(value: date) -> datetime:
    return datetime.combine(value, datetime.min.time(), tzinfo=UTC)
