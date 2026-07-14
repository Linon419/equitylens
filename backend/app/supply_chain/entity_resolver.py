import hashlib
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from app.supply_chain.schemas import (
    EdgeType,
    EntityCandidate,
    EvidenceReference,
    EvidenceStatus,
    GraphDraft,
    GraphEdgeDraft,
    GraphNodeDraft,
    ResolutionBasis,
    ResolvedEntity,
)

_SYMBOL = re.compile(r"^[A-Z0-9.-]{1,16}$")
_CIK = re.compile(r"^[0-9]{10}$")
_BASIS_RANK: dict[ResolutionBasis, int] = {
    "cik": 0,
    "ticker": 1,
    "legal_name": 2,
    "deterministic_key": 3,
    "unresolved_hash": 4,
    "ambiguous_name": 5,
}
_STATUS_RANK = {"verified": 0, "potential": 1, "internal": 2}


@dataclass(frozen=True, slots=True)
class CompanyDirectoryEntry:
    company_id: int
    symbol: str
    cik: str
    legal_name: str
    aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.company_id < 1:
            raise ValueError("company_id must be positive")
        if _SYMBOL.fullmatch(self.symbol) is None:
            raise ValueError("symbol is invalid")
        if _CIK.fullmatch(self.cik) is None:
            raise ValueError("CIK is invalid")
        if not self.legal_name.strip():
            raise ValueError("legal_name is required")
        names = [_normalized_label(value) for value in self.aliases]
        if any(not value for value in names) or len(names) != len(set(names)):
            raise ValueError("aliases must be non-empty and unique")


class DeterministicEntityResolver:
    def __init__(self, directory: tuple[CompanyDirectoryEntry, ...]) -> None:
        self._by_cik: dict[str, CompanyDirectoryEntry] = {}
        self._by_symbol: dict[str, CompanyDirectoryEntry] = {}
        self._by_name: dict[str, list[CompanyDirectoryEntry]] = defaultdict(list)
        for entry in directory:
            if entry.cik in self._by_cik:
                raise ValueError(f"duplicate CIK: {entry.cik}")
            if entry.symbol in self._by_symbol:
                raise ValueError(f"duplicate symbol: {entry.symbol}")
            self._by_cik[entry.cik] = entry
            self._by_symbol[entry.symbol] = entry
            names = {
                _normalized_label(name) for name in (entry.legal_name, *entry.aliases)
            }
            for name in names:
                self._by_name[name].append(entry)

    async def resolve(self, candidate: EntityCandidate) -> ResolvedEntity:
        if candidate.kind != "company":
            return ResolvedEntity(
                node_key=non_company_node_key(candidate.kind, candidate.label_en),
                resolution_status="resolved",
                resolution_basis="deterministic_key",
                confidence=1.0,
            )
        if candidate.cik is not None and candidate.cik in self._by_cik:
            return _resolved_company(self._by_cik[candidate.cik], basis="cik")
        if candidate.symbol is not None and candidate.symbol in self._by_symbol:
            return _resolved_company(
                self._by_symbol[candidate.symbol],
                basis="ticker",
            )
        normalized_name = _normalized_label(candidate.label_en)
        name_matches = self._by_name.get(normalized_name, [])
        if len(name_matches) == 1:
            return _resolved_company(name_matches[0], basis="legal_name")
        unresolved_identity = "\0".join(
            (normalized_name, candidate.symbol or "", candidate.cik or "")
        )
        digest = hashlib.sha256(unresolved_identity.encode()).hexdigest()[:12]
        ambiguous = len(name_matches) > 1
        return ResolvedEntity(
            node_key=f"company:unresolved:{digest}",
            symbol=candidate.symbol,
            cik=candidate.cik,
            resolution_status="ambiguous" if ambiguous else "unresolved",
            resolution_basis="ambiguous_name" if ambiguous else "unresolved_hash",
            confidence=0.4 if ambiguous else 0.5,
        )

    async def resolve_draft(self, draft: GraphDraft) -> GraphDraft:
        node_groups: dict[
            str,
            list[tuple[GraphNodeDraft, ResolvedEntity]],
        ] = defaultdict(list)
        redirects: dict[str, str] = {}
        for node in draft.nodes:
            resolved = await self.resolve(
                EntityCandidate(
                    node_key=node.node_key,
                    kind=node.kind,
                    label_en=node.label_en,
                    symbol=node.symbol,
                    cik=node.cik,
                )
            )
            redirects[node.node_key] = resolved.node_key
            node_groups[resolved.node_key].append((node, resolved))

        nodes = [
            _merge_node(
                node_key,
                members,
                focus_node_key=draft.focus_node_key,
            )
            for node_key, members in node_groups.items()
        ]
        nodes.sort(key=lambda node: (node.rank, node.node_key))
        edges = _merge_edges(draft.edges, redirects)
        return GraphDraft(
            focus_node_key=redirects[draft.focus_node_key],
            thesis_en=draft.thesis_en,
            nodes=nodes,
            edges=edges,
        )


def non_company_node_key(
    kind: Literal["business", "product", "category"],
    label: str,
) -> str:
    normalized = _normalized_label(label)
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-") or "entity"
    digest = hashlib.sha256(normalized.encode()).hexdigest()[:10]
    return f"{kind}:{slug[:48]}:{digest}"


def _resolved_company(
    entry: CompanyDirectoryEntry,
    *,
    basis: Literal["cik", "ticker", "legal_name"],
) -> ResolvedEntity:
    confidence = {"cik": 1.0, "ticker": 0.98, "legal_name": 0.9}[basis]
    return ResolvedEntity(
        node_key=f"company:{entry.cik}",
        company_id=entry.company_id,
        symbol=entry.symbol,
        cik=entry.cik,
        legal_name=entry.legal_name,
        resolution_status="resolved",
        resolution_basis=basis,
        confidence=confidence,
    )


def _merge_node(
    node_key: str,
    members: list[tuple[GraphNodeDraft, ResolvedEntity]],
    *,
    focus_node_key: str,
) -> GraphNodeDraft:
    ordered = sorted(
        members,
        key=lambda item: (
            _BASIS_RANK[item[1].resolution_basis],
            -item[0].importance,
            -item[0].confidence,
            item[0].node_key,
        ),
    )
    _, selected_entity = ordered[0]
    focus_members = [node for node, _ in members if node.node_key == focus_node_key]
    content_node = (
        focus_members[0]
        if focus_members
        else sorted(
            (node for node, _ in members),
            key=lambda node: (
                -node.importance,
                -node.confidence,
                node.rank,
                node.node_key,
            ),
        )[0]
    )
    canonical_label = selected_entity.legal_name or content_node.label_en
    aliases = _merged_aliases(members, canonical_label=canonical_label)
    return GraphNodeDraft(
        node_key=node_key,
        kind=content_node.kind,
        layer=content_node.layer,
        label_en=canonical_label,
        description_en=content_node.description_en,
        company_id=selected_entity.company_id,
        symbol=selected_entity.symbol,
        cik=selected_entity.cik,
        importance=max(node.importance for node, _ in members),
        confidence=min(
            max(node.confidence for node, _ in members),
            selected_entity.confidence,
        ),
        rank=min(node.rank for node, _ in members),
        aliases=aliases,
        resolution_status=selected_entity.resolution_status,
        resolution_basis=selected_entity.resolution_basis,
    )


def _merge_edges(
    edges: list[GraphEdgeDraft],
    redirects: dict[str, str],
) -> list[GraphEdgeDraft]:
    groups: dict[tuple[str, str, EdgeType], list[GraphEdgeDraft]] = defaultdict(list)
    for edge in edges:
        source_key = redirects[edge.source_node_key]
        target_key = redirects[edge.target_node_key]
        if source_key == target_key:
            continue
        groups[(source_key, target_key, edge.relationship_type)].append(edge)

    merged = [_merge_edge(identity, members) for identity, members in groups.items()]
    return sorted(merged, key=lambda edge: edge.edge_key)


def _merge_edge(
    identity: tuple[str, str, EdgeType],
    members: list[GraphEdgeDraft],
) -> GraphEdgeDraft:
    source_key, target_key, relationship_type = identity
    selected = sorted(
        members,
        key=lambda edge: (
            _STATUS_RANK[edge.evidence_status],
            -edge.confidence,
            -edge.importance,
            edge.edge_key,
        ),
    )[0]
    evidence = _deduplicate_evidence(
        members,
        preferred_status=selected.evidence_status,
    )
    digest_input = f"{source_key}\0{target_key}\0{relationship_type}"
    digest = hashlib.sha256(digest_input.encode()).hexdigest()[:16]
    return GraphEdgeDraft(
        edge_key=f"edge:{relationship_type}:{digest}",
        source_node_key=source_key,
        target_node_key=target_key,
        relationship_type=relationship_type,
        evidence_status=selected.evidence_status,
        confidence=max(edge.confidence for edge in members),
        importance=max(edge.importance for edge in members),
        explanation_en=selected.explanation_en,
        evidence_refs=evidence,
    )


def _deduplicate_evidence(
    members: list[GraphEdgeDraft],
    *,
    preferred_status: EvidenceStatus,
) -> list[EvidenceReference]:
    evidence: dict[
        tuple[str, str, str, str],
        tuple[bool, EvidenceReference],
    ] = {}
    for edge in members:
        preferred = edge.evidence_status == preferred_status
        for reference in edge.evidence_refs:
            identity = (
                reference.source_key,
                reference.excerpt,
                reference.locator,
                reference.support_role,
            )
            current = evidence.get(identity)
            if (
                current is None
                or (preferred and not current[0])
                or (
                    preferred == current[0]
                    and reference.confidence > current[1].confidence
                )
            ):
                evidence[identity] = (preferred, reference)
    ordered = sorted(
        evidence.items(),
        key=lambda item: (not item[1][0], -item[1][1].confidence, item[0]),
    )
    return [record[1] for _, record in ordered[:12]]


def _merged_aliases(
    members: list[tuple[GraphNodeDraft, ResolvedEntity]],
    *,
    canonical_label: str,
) -> list[str]:
    canonical = _normalized_label(canonical_label)
    candidates = sorted(
        (alias for node, _ in members for alias in (node.label_en, *node.aliases)),
        key=lambda alias: (len(alias), _normalized_label(alias), alias),
    )
    aliases: dict[str, str] = {}
    for alias in candidates:
        normalized = _normalized_label(alias)
        if normalized != canonical:
            aliases.setdefault(normalized, alias)
    return list(aliases.values())[:24]


def _normalized_label(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.sub(r"[^\w]+", " ", normalized).split())
