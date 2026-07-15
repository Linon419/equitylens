from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.chat.schemas import (
    BusinessClaimContext,
    ConversationCreate,
    FinancialMetricContext,
    MarketMetricContext,
    MessageCreate,
    SupplyChainEdgeContext,
    SupplyChainNodeContext,
)


def test_message_request_normalizes_unicode_whitespace() -> None:
    request = MessageCreate(
        client_request_id=uuid4(),
        content="  Why\u00a0did  margins rise?  ",
        locale="en-US",
        context=[],
    )

    assert request.content == "Why did margins rise?"


def test_message_request_enforces_length_and_closed_context_union() -> None:
    with pytest.raises(ValidationError, match="at most 2000"):
        MessageCreate(
            client_request_id=uuid4(),
            content="a" * 2_001,
            locale="en-US",
            context=[],
        )

    with pytest.raises(ValidationError):
        MessageCreate(
            client_request_id=uuid4(),
            content="Question",
            locale="en-US",
            context=[{"kind": "client_text", "id": str(uuid4())}],
        )


def test_context_selections_require_typed_server_identifiers() -> None:
    snapshot_id = uuid4()
    object_id = uuid4()
    request = MessageCreate(
        client_request_id=uuid4(),
        content="Explain these items.",
        locale="zh-CN",
        context=[
            MarketMetricContext(
                metric_key="trailing_pe",
                observed_at=datetime(2026, 7, 15, tzinfo=UTC),
            ),
            FinancialMetricContext(metric_key="revenue", period_key="FY2025"),
            BusinessClaimContext(id="business-1", snapshot_id=snapshot_id),
            SupplyChainNodeContext(id=object_id, snapshot_id=snapshot_id),
            SupplyChainEdgeContext(id=object_id, snapshot_id=snapshot_id),
        ],
    )

    assert [item.kind for item in request.context] == [
        "market_metric",
        "financial_metric",
        "business_claim",
        "supply_chain_node",
        "supply_chain_edge",
    ]
    with pytest.raises(ValidationError):
        BusinessClaimContext(id=str(object_id), snapshot_id=snapshot_id)
    with pytest.raises(ValidationError):
        MessageCreate(
            client_request_id=uuid4(),
            content="Question",
            locale="en-US",
            context=[
                {
                    "kind": "supply_chain_edge",
                    "id": "edge-from-client-label",
                    "snapshot_id": str(snapshot_id),
                }
            ],
        )


def test_conversation_create_has_strict_locale_and_title() -> None:
    assert ConversationCreate(locale="en-US").title is None
    assert ConversationCreate(locale="zh-CN", title=" 苹果研究 ").title == "苹果研究"

    with pytest.raises(ValidationError):
        ConversationCreate(locale="fr-FR")
    with pytest.raises(ValidationError):
        ConversationCreate(locale="en-US", title="x" * 121)
