from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from sqlmodel import Session

from app.chat.schemas import (
    BusinessClaimContext,
    FinancialMetricContext,
    MarketMetricContext,
    SupplyChainEdgeContext,
    SupplyChainNodeContext,
)
from app.chat.structured_context import StructuredContextService
from app.core.errors import DomainError
from app.models.chat_model import FilingChunk
from app.models.company_model import Company
from app.models.market_model import FinancialMetric, MarketSnapshot
from app.models.research_model import (
    CompanyIntelligenceSnapshot,
    EvidenceCitation,
    Filing,
    FilingSection,
)
from app.models.supply_chain_model import (
    GraphEdgeCitation,
    GraphOfficialSource,
    SupplyChainGraphEdge,
    SupplyChainGraphNode,
    SupplyChainGraphSnapshot,
)

NOW = datetime(2026, 7, 15, 12, tzinfo=UTC)
SEC_URL = "https://www.sec.gov/Archives/example/aapl-2025.htm"
GRAPH_EXCERPT = "TSMC fabricates Apple-designed silicon used across products."


@dataclass(frozen=True)
class SeededContext:
    intelligence_id: UUID
    graph_id: UUID
    node_id: UUID
    edge_id: UUID


@pytest.fixture
def seeded_context(chat_session: Session) -> SeededContext:
    _seed_market(chat_session)
    _seed_financials(chat_session)
    filing, section = _seed_filing(chat_session)
    intelligence_id = _seed_intelligence(chat_session, filing, section)
    graph_id, node_id, edge_id = _seed_graph(chat_session)
    chat_session.commit()
    return SeededContext(intelligence_id, graph_id, node_id, edge_id)


@pytest.mark.asyncio
async def test_latest_market_and_four_year_financial_window_are_resolved(
    chat_session: Session,
    seeded_context: SeededContext,
) -> None:
    del seeded_context
    service = StructuredContextService(chat_session, now=NOW)
    company = chat_session.get(Company, 1)
    assert company is not None

    pack = await service.resolve(
        company=company,
        selections=[
            MarketMetricContext(metric_key="price", observed_at=NOW),
            FinancialMetricContext(metric_key="revenue", period_key="FY2025"),
        ],
        locale="en-US",
    )

    assert [item.label for item in pack.items] == ["Price", "Revenue · FY2025"]
    assert pack.items[0].citation.attributes["value"] == "225.50"
    assert pack.items[0].citation.published_at == NOW
    trailing_pe = next(
        evidence
        for evidence in pack.evidence
        if evidence.attributes.get("metric_key") == "trailing_pe"
    )
    assert trailing_pe.excerpt == "AAPL Trailing P/E was 31.32 x."
    assert trailing_pe.attributes["unit"] == "x"
    revenue_periods = [
        evidence.attributes["period_key"]
        for evidence in pack.evidence
        if evidence.attributes.get("metric_key") == "revenue"
    ]
    assert revenue_periods == ["FY2022", "FY2023", "FY2024", "FY2025", "TTM"]
    assert pack.readiness.intelligence.state == "ready"
    assert pack.readiness.filing_text.state == "ready"
    assert pack.readiness.filing_index.state == "ready"
    assert pack.readiness.supply_chain_graph.state == "ready"


@pytest.mark.asyncio
async def test_newer_20_f_drives_filing_readiness(
    chat_session: Session,
    seeded_context: SeededContext,
) -> None:
    del seeded_context
    filing = Filing(
        company_id=1,
        accession_number="0001577552-26-000001",
        form="20-F",
        fiscal_period="FY2026",
        filed_at=date(2026, 5, 20),
        report_date=date(2026, 3, 31),
        primary_document="baba-20260331.htm",
        source_url="https://www.sec.gov/Archives/baba-20260331.htm",
    )
    chat_session.add(filing)
    chat_session.flush()
    chat_session.add(
        FilingSection(
            filing_id=filing.id,
            heading="Item 4. Information on the Company",
            source_anchor="item-4",
            ordinal=0,
            text="Commerce and cloud platforms serve customers worldwide.",
        )
    )
    chat_session.commit()
    company = chat_session.get(Company, 1)
    assert company is not None

    pack = await StructuredContextService(chat_session, now=NOW).resolve(
        company=company,
        selections=[],
        locale="en-US",
    )

    assert pack.readiness.filing_text.state == "ready"
    assert pack.readiness.filing_index.state == "missing"
    assert pack.readiness.filing_index.action == "filing_index"


@pytest.mark.asyncio
async def test_business_claim_uses_persisted_localization_and_excerpt(
    chat_session: Session,
    seeded_context: SeededContext,
) -> None:
    company = chat_session.get(Company, 1)
    assert company is not None

    pack = await StructuredContextService(chat_session, now=NOW).resolve(
        company=company,
        selections=[
            BusinessClaimContext(
                id="business-1",
                snapshot_id=seeded_context.intelligence_id,
            )
        ],
        locale="zh-CN",
    )

    item = pack.items[0]
    assert item.label == "设备与服务"
    assert item.description == "硬件连接服务生态。"
    assert item.citation.excerpt == "Devices and services drive revenue."
    assert item.citation.source_url == f"{SEC_URL}#item-1"


@pytest.mark.asyncio
async def test_graph_node_and_edge_use_published_server_records(
    chat_session: Session,
    seeded_context: SeededContext,
) -> None:
    company = chat_session.get(Company, 1)
    assert company is not None

    pack = await StructuredContextService(chat_session, now=NOW).resolve(
        company=company,
        selections=[
            SupplyChainNodeContext(
                id=seeded_context.node_id,
                snapshot_id=seeded_context.graph_id,
            ),
            SupplyChainEdgeContext(
                id=seeded_context.edge_id,
                snapshot_id=seeded_context.graph_id,
            ),
        ],
        locale="en-US",
    )

    assert pack.items[0].label == "TSMC"
    assert pack.items[0].citation.excerpt == GRAPH_EXCERPT
    assert pack.items[1].label == "TSMC supplies Apple silicon"
    assert pack.items[1].citation.excerpt == GRAPH_EXCERPT
    assert all(item.citation.source_tier == "primary" for item in pack.items)


@pytest.mark.asyncio
async def test_stale_and_cross_company_context_have_stable_error(
    chat_session: Session,
    seeded_context: SeededContext,
) -> None:
    stale = SupplyChainGraphSnapshot(
        company_id=1,
        status="completed",
        schema_version="v1",
        prompt_version="p1",
        model_id="test",
        source_fingerprint="b" * 64,
        content_en={},
        content_zh={},
        evidence_coverage="partial",
        node_count=0,
        edge_count=0,
        generated_at=NOW - timedelta(days=10),
        completed_at=NOW - timedelta(days=10),
    )
    chat_session.add(stale)
    chat_session.commit()
    aapl = chat_session.get(Company, 1)
    msft = chat_session.get(Company, 2)
    assert aapl is not None and msft is not None
    service = StructuredContextService(chat_session, now=NOW)

    with pytest.raises(DomainError, match="CHAT_CONTEXT_INVALID"):
        await service.resolve(
            company=aapl,
            selections=[
                SupplyChainEdgeContext(
                    id=seeded_context.edge_id,
                    snapshot_id=stale.id,
                )
            ],
            locale="en-US",
        )
    with pytest.raises(DomainError, match="CHAT_CONTEXT_INVALID"):
        await service.resolve(
            company=msft,
            selections=[
                BusinessClaimContext(
                    id="business-1",
                    snapshot_id=seeded_context.intelligence_id,
                )
            ],
            locale="en-US",
        )


@pytest.mark.asyncio
async def test_missing_resources_return_actions_and_evidence_gaps(
    chat_session: Session,
) -> None:
    company = chat_session.get(Company, 2)
    assert company is not None

    pack = await StructuredContextService(chat_session, now=NOW).resolve(
        company=company,
        selections=[],
        locale="en-US",
    )

    assert pack.readiness.intelligence.action == "company_analysis"
    assert pack.readiness.filing_text.action == "filing_index"
    assert pack.readiness.filing_index.action == "filing_index"
    assert pack.readiness.supply_chain_graph.action == "supply_chain_graph"
    assert pack.readiness.web_recency.state == "missing"
    assert {gap.resource for gap in pack.gaps} >= {
        "market",
        "financials",
        "intelligence",
        "filing_text",
        "filing_index",
        "supply_chain_graph",
        "web_recency",
    }


def _seed_market(session: Session) -> None:
    session.add_all(
        [
            MarketSnapshot(
                company_id=1,
                price=Decimal("200"),
                provider="yahoo",
                observed_at=NOW - timedelta(days=1),
                fetched_at=NOW - timedelta(days=1),
            ),
            MarketSnapshot(
                company_id=1,
                price=Decimal("225.50"),
                market_cap=Decimal("3400000000000"),
                trailing_eps=Decimal("7.20"),
                trailing_pe=Decimal("31.32"),
                forward_pe=Decimal("28.10"),
                provider="yahoo",
                observed_at=NOW,
                fetched_at=NOW,
            ),
        ]
    )


def _seed_financials(session: Session) -> None:
    for index, period in enumerate(("FY2022", "FY2023", "FY2024", "FY2025", "TTM")):
        fiscal_period = "TTM" if period == "TTM" else "FY"
        session.add(
            FinancialMetric(
                company_id=1,
                metric_key="revenue",
                fiscal_year=2025 if period == "TTM" else 2022 + index,
                fiscal_period=fiscal_period,
                period_key=period,
                start_date=date(2021 + index, 10, 1),
                end_date=date(2022 + index, 9, 30),
                value=Decimal(390_000_000_000 + index * 10_000_000_000),
                unit="USD",
                taxonomy_tag="Revenues",
                accession_number=f"0000320193-2{index}-000001",
                filed_at=date(2022 + index, 10, 31),
                source_url="https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json",
                fetched_at=NOW,
            )
        )


def _seed_filing(session: Session) -> tuple[Filing, FilingSection]:
    filing = Filing(
        company_id=1,
        accession_number="0000320193-25-000079",
        form="10-K",
        fiscal_period="FY2025",
        filed_at=date(2025, 10, 31),
        report_date=date(2025, 9, 27),
        primary_document="aapl-2025.htm",
        source_url=SEC_URL,
    )
    session.add(filing)
    session.flush()
    section = FilingSection(
        filing_id=filing.id,
        heading="Item 1. Business",
        source_anchor="item-1",
        ordinal=0,
        text="Devices and services drive revenue for Apple customers worldwide.",
    )
    session.add(section)
    session.flush()
    session.add(
        FilingChunk(
            company_id=1,
            filing_id=filing.id,
            section_id=section.id,
            ordinal=0,
            text=section.text,
            token_count=9,
            content_hash="a" * 64,
            chunk_schema_version="filing-chunk.v1",
            embedding_model="text-embedding-3-small",
            embedding=[0.1] * 1_536,
        )
    )
    return filing, section


def _seed_intelligence(
    session: Session,
    filing: Filing,
    section: FilingSection,
) -> UUID:
    citation = {
        "citation_id": "citation-1",
        "section_id": str(section.id),
        "excerpt": "Devices and services drive revenue.",
    }
    claim_en = {
        "claim_id": "business-1",
        "title": "Devices and services",
        "explanation": "Hardware connects a services ecosystem.",
        "confidence": "High",
        "citation_ids": ["citation-1"],
    }
    claim_zh = {
        **claim_en,
        "title": "设备与服务",
        "explanation": "硬件连接服务生态。",
    }
    empty = {
        "revenue_engines": [],
        "upstream": [],
        "company_layer": [],
        "downstream": [],
        "competitors": [],
        "material_dependencies": [],
        "citations": [citation],
        "evidence_coverage": "complete",
        "overall_confidence": "High",
    }
    snapshot = CompanyIntelligenceSnapshot(
        company_id=1,
        filing_id=filing.id,
        status="completed",
        evidence_coverage="complete",
        schema_version="v1",
        prompt_version="p1",
        model_id="test",
        content_en={**empty, "locale": "en", "core_businesses": [claim_en]},
        content_zh={**empty, "locale": "zh", "core_businesses": [claim_zh]},
        overall_confidence="High",
        generated_at=NOW,
        verified_at=NOW,
    )
    session.add(snapshot)
    session.flush()
    session.add(
        EvidenceCitation(
            snapshot_id=snapshot.id,
            filing_id=filing.id,
            section_label=section.heading,
            source_anchor=section.source_anchor,
            excerpt=citation["excerpt"],
            source_url=filing.source_url,
            verification_verdict="supported",
        )
    )
    return snapshot.id


def _seed_graph(session: Session) -> tuple[UUID, UUID, UUID]:
    snapshot = SupplyChainGraphSnapshot(
        company_id=1,
        status="completed",
        schema_version="v1",
        prompt_version="p1",
        model_id="test",
        source_fingerprint="a" * 64,
        content_en={},
        content_zh={},
        evidence_coverage="complete",
        overall_confidence="High",
        node_count=2,
        edge_count=1,
        generated_at=NOW,
        verified_at=NOW,
        completed_at=NOW,
    )
    session.add(snapshot)
    session.flush()
    supplier = SupplyChainGraphNode(
        snapshot_id=snapshot.id,
        node_key="company:tsmc",
        kind="company",
        layer="upstream",
        label_en="TSMC",
        label_zh="台积电",
        description_en="Semiconductor foundry supplier.",
        description_zh="半导体晶圆代工商。",
        importance=Decimal("0.9"),
        confidence="High",
        rank=0,
    )
    apple = SupplyChainGraphNode(
        snapshot_id=snapshot.id,
        node_key="company:apple",
        kind="company",
        layer="core",
        company_id=1,
        symbol="AAPL",
        cik="0000320193",
        label_en="Apple",
        label_zh="苹果",
        description_en="Designs products and services.",
        description_zh="设计产品与服务。",
        importance=Decimal("1"),
        confidence="High",
        rank=0,
    )
    session.add_all([supplier, apple])
    session.flush()
    edge = SupplyChainGraphEdge(
        snapshot_id=snapshot.id,
        edge_key="tsmc-supplies-apple",
        source_node_id=supplier.id,
        target_node_id=apple.id,
        relationship_type="supplies",
        evidence_status="verified",
        confidence="High",
        explanation_en="TSMC supplies Apple silicon",
        explanation_zh="台积电为苹果供应芯片",
    )
    source = GraphOfficialSource(
        snapshot_id=snapshot.id,
        source_type="annual_report",
        publisher="Apple Inc.",
        title="Apple Supplier List",
        canonical_url="https://www.apple.com/supplier-responsibility/",
        published_at=date(2025, 3, 15),
        fetched_at=NOW,
        content_hash="c" * 64,
        artifact_key="fixtures/apple-suppliers.txt",
    )
    session.add_all([edge, source])
    session.flush()
    session.add(
        GraphEdgeCitation(
            snapshot_id=snapshot.id,
            edge_id=edge.id,
            source_id=source.id,
            excerpt=GRAPH_EXCERPT,
            source_anchor="supplier-list-tsmc",
            support_role="primary",
        )
    )
    return snapshot.id, supplier.id, edge.id
