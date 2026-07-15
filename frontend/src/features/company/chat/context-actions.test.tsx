import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BusinessSummary } from "../business-summary";
import { companyPageCopy } from "../copy";
import { FinancialTable } from "../financial-table";
import { MarketContext } from "../market-context";
import { SupplyChainInspector } from "../supply-chain-inspector";
import {
  financialsFixture,
  intelligenceFixture,
  marketFixture,
  supplyChainGraphCachedFixture,
} from "../test-fixtures";

describe("typed chat context actions", () => {
  afterEach(cleanup);

  it("selects market and valuation metrics with observation time", async () => {
    const user = userEvent.setup();
    const onAskContext = vi.fn();
    render(
      <MarketContext
        copy={companyPageCopy.en.market}
        data={marketFixture}
        locale="en-US"
        onAskContext={onAskContext}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Ask EquityLens: Share price/ }));
    await user.click(screen.getByRole("button", { name: /Ask EquityLens: Trailing P\/E/ }));

    expect(onAskContext).toHaveBeenNthCalledWith(1, {
      key: "market_metric:price",
      label: "Share price",
      selection: {
        kind: "market_metric",
        metric_key: "price",
        observed_at: marketFixture.observed_at,
      },
    });
    expect(onAskContext.mock.calls[1][0].selection.metric_key).toBe("trailing_pe");
  });

  it("selects a financial metric and fiscal period", async () => {
    const user = userEvent.setup();
    const onAskContext = vi.fn();
    render(
      <FinancialTable
        askLabel={companyPageCopy.en.financials.ask}
        data={financialsFixture}
        locale="en"
        onAskContext={onAskContext}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Ask EquityLens: Revenue FY 2022/ }));
    expect(onAskContext).toHaveBeenCalledWith({
      key: "financial_metric:revenue:FY2022",
      label: "Revenue · FY 2022",
      selection: {
        kind: "financial_metric",
        metric_key: "revenue",
        period_key: "FY2022",
      },
    });
  });

  it("selects a published business claim", async () => {
    const user = userEvent.setup();
    const onAskContext = vi.fn();
    render(
      <BusinessSummary
        citations={intelligenceFixture.citations}
        claims={intelligenceFixture.content.core_businesses}
        copy={companyPageCopy.en.business}
        onAskContext={onAskContext}
        onCitation={vi.fn()}
        snapshotId={intelligenceFixture.snapshot_id}
      />,
    );

    await user.click(
      screen.getByRole("button", { name: /Ask EquityLens: Devices and services/ }),
    );
    expect(onAskContext).toHaveBeenCalledWith({
      key: `business_claim:business-1:${intelligenceFixture.snapshot_id}`,
      label: "Devices and services",
      selection: {
        kind: "business_claim",
        id: "business-1",
        snapshot_id: intelligenceFixture.snapshot_id,
      },
    });
  });

  it("selects graph nodes and relationships from the evidence inspector", async () => {
    const user = userEvent.setup();
    const onAskContext = vi.fn();
    const graph = supplyChainGraphCachedFixture;
    const node = graph.nodes[0];
    const edge = graph.edges[0];
    const props = {
      copy: companyPageCopy.en.graph,
      directEdges: [],
      locale: "en-US",
      nodes: graph.nodes,
      onAskContext,
      onCenterCompany: vi.fn(),
      onClose: vi.fn(),
      snapshotId: graph.snapshot.id,
      sources: graph.sources,
    };
    const view = render(
      <SupplyChainInspector {...props} selection={{ type: "node", value: node }} />,
    );

    await user.click(screen.getByRole("button", { name: /Ask EquityLens: Supplier 1/ }));
    expect(onAskContext).toHaveBeenCalledWith({
      key: `supply_chain_node:${node.id}:${graph.snapshot.id}`,
      label: node.label,
      selection: {
        kind: "supply_chain_node",
        id: node.id,
        snapshot_id: graph.snapshot.id,
      },
    });

    view.rerender(
      <SupplyChainInspector {...props} selection={{ type: "edge", value: edge }} />,
    );
    await user.click(
      screen.getByRole("button", { name: /Ask EquityLens about this relationship/ }),
    );
    expect(onAskContext.mock.calls[1][0].selection).toEqual({
      kind: "supply_chain_edge",
      id: edge.id,
      snapshot_id: graph.snapshot.id,
    });
  });
});
