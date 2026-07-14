from datetime import UTC, datetime

import pytest
from sqlmodel import Session, select

from app.core.errors import DomainError
from app.models.company_model import Company
from app.models.job_model import IngestionJob
from app.models.supply_chain_model import SupplyChainGraphSnapshot
from app.quota.identity import RequestPrincipal
from app.quota.repository import InMemoryQuotaRepository
from app.supply_chain.repository import (
    CreateWorkingSnapshotCommand,
    PublishGraphCommand,
    SqlSupplyChainGraphRepository,
)
from app.supply_chain.schemas import (
    AcceptedGraph,
    GraphLocalization,
    OfficialSourceDocument,
)
from app.supply_chain.service import SupplyChainGraphService

NOW = datetime(2026, 7, 14, 12, tzinfo=UTC)
GUEST = RequestPrincipal.guest("guest-hash", "ip-hash")


def working_command(
    company: Company,
    sources: list[OfficialSourceDocument],
) -> CreateWorkingSnapshotCommand:
    assert company.id is not None
    return CreateWorkingSnapshotCommand(
        company_id=company.id,
        sources=sources,
        source_fingerprint="a" * 64,
        schema_version="supply-chain-graph.v1",
        prompt_version="supply-chain-graph.2026-07-14",
        model_id="gpt-5-mini",
        now=NOW,
    )


@pytest.fixture
def published_service(
    session: Session,
    company: Company,
    source_documents: list[OfficialSourceDocument],
    accepted_graph: AcceptedGraph,
    graph_localization: GraphLocalization,
) -> SupplyChainGraphService:
    repository = SqlSupplyChainGraphRepository(session)
    working = repository.create_working_snapshot(
        working_command(company, source_documents)
    )
    repository.publish(
        PublishGraphCommand(
            snapshot_id=working.id,
            graph=accepted_graph,
            localization=graph_localization,
            now=NOW,
        )
    )
    return SupplyChainGraphService(
        session=session,
        repository=repository,
        quota_repository=InMemoryQuotaRepository(),
        now=NOW,
    )


def test_current_graph_defaults_to_verified_edges(
    published_service: SupplyChainGraphService,
    company: Company,
) -> None:
    graph = published_service.get_current(
        company=company,
        principal=GUEST,
        locale="en",
    )

    assert graph.snapshot.symbol == "AAPL"
    assert graph.snapshot.status == "completed"
    assert graph.edges
    assert all(edge.evidence_status == "verified" for edge in graph.edges)
    assert graph.refresh_job is None
    assert graph.quota.used == 0
    assert {source.id for source in graph.sources} == {
        citation.source_id for edge in graph.edges for citation in edge.citations
    }


def test_potential_toggle_and_chinese_locale_use_bilingual_content(
    published_service: SupplyChainGraphService,
    company: Company,
) -> None:
    graph = published_service.get_current(
        company=company,
        principal=GUEST,
        locale="zh",
        evidence={"verified", "potential"},
    )

    assert graph.snapshot.thesis.startswith("中文")
    assert any(edge.evidence_status == "potential" for edge in graph.edges)
    assert all(node.description.startswith("中文说明") for node in graph.nodes)
    assert all(edge.explanation.startswith("中文说明") for edge in graph.edges)


@pytest.mark.parametrize(("requested", "expected_max"), [(1, 10), (99, 40)])
def test_node_limit_is_clamped_and_all_edges_keep_selected_endpoints(
    published_service: SupplyChainGraphService,
    company: Company,
    requested: int,
    expected_max: int,
) -> None:
    graph = published_service.get_current(
        company=company,
        principal=GUEST,
        locale="en",
        evidence={"verified", "potential"},
        limit=requested,
    )

    node_ids = {node.id for node in graph.nodes}
    assert len(graph.nodes) <= expected_max
    assert graph.snapshot.focus_node_key in {node.node_key for node in graph.nodes}
    assert all({edge.source, edge.target} <= node_ids for edge in graph.edges)
    if expected_max == 10:
        assert {node.layer for node in graph.nodes} == {
            "upstream",
            "core",
            "downstream",
        }


def test_active_refresh_is_returned_with_previous_snapshot(
    session: Session,
    published_service: SupplyChainGraphService,
    company: Company,
) -> None:
    assert company.id is not None
    job = IngestionJob(
        job_type="supply_chain_graph",
        company_id=company.id,
        requested_by_type="guest",
        requested_by_hash=GUEST.principal_hash,
        deduplication_key="supply-chain-graph:active",
        state="extracting",
        current_step="extracting",
        created_at=NOW,
        updated_at=NOW,
    )
    session.add(job)
    session.commit()

    graph = published_service.get_current(
        company=company,
        principal=GUEST,
        locale="en",
    )

    assert graph.refresh_job is not None
    assert graph.refresh_job.id == job.id
    assert graph.snapshot.status == "completed"


@pytest.mark.parametrize(
    ("locale", "evidence", "code"),
    [
        ("fr", {"verified"}, "GRAPH_LOCALE_INVALID"),
        ("en", {"internal"}, "GRAPH_EVIDENCE_FILTER_INVALID"),
        ("en", set(), "GRAPH_EVIDENCE_FILTER_INVALID"),
    ],
)
def test_invalid_public_filters_raise_stable_domain_errors(
    published_service: SupplyChainGraphService,
    company: Company,
    locale: str,
    evidence: set[str],
    code: str,
) -> None:
    with pytest.raises(DomainError) as error:
        published_service.get_current(
            company=company,
            principal=GUEST,
            locale=locale,
            evidence=evidence,
        )

    assert error.value.code == code
    assert error.value.status_code == 422


def test_missing_graph_raises_not_found(
    session: Session,
    company: Company,
) -> None:
    service = SupplyChainGraphService(
        session=session,
        repository=SqlSupplyChainGraphRepository(session),
        quota_repository=InMemoryQuotaRepository(),
        now=NOW,
    )

    with pytest.raises(DomainError) as error:
        service.get_current(company=company, principal=GUEST, locale="en")

    assert error.value.code == "GRAPH_NOT_FOUND"
    assert error.value.status_code == 404


def test_missing_citation_audit_fails_with_stable_server_error(
    session: Session,
    published_service: SupplyChainGraphService,
    company: Company,
) -> None:
    snapshot = session.exec(
        select(SupplyChainGraphSnapshot).where(
            SupplyChainGraphSnapshot.company_id == company.id
        )
    ).one()
    snapshot.content_en = {
        **snapshot.content_en,
        "public_edges": [],
        "potential_edges": [],
    }
    session.add(snapshot)
    session.commit()

    with pytest.raises(DomainError) as error:
        published_service.get_current(
            company=company,
            principal=GUEST,
            locale="en",
        )

    assert error.value.code == "GRAPH_CITATION_AUDIT_MISSING"
    assert error.value.status_code == 500
