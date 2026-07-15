import React from "react";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@xyflow/react", () => ({
  Background: () => null,
  BaseEdge: () => null,
  Controls: () => null,
  Handle: () => null,
  MarkerType: { ArrowClosed: "arrowclosed" },
  MiniMap: () => null,
  Panel: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  Position: { Left: "left", Right: "right" },
  ReactFlowProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  ReactFlow: ({
    children,
    edges,
    nodeTypes,
    nodes,
    onNodeClick,
  }: {
    children: React.ReactNode;
    edges: Array<{ id: string }>;
    nodeTypes: Record<string, React.ComponentType<Record<string, unknown>>>;
    nodes: Array<{
      data: Record<string, unknown>;
      id: string;
      selected?: boolean;
      type: string;
    }>;
    onNodeClick: (event: React.MouseEvent, node: { id: string }) => void;
  }) => (
    <div data-edge-count={edges.length} data-testid="react-flow-canvas">
      {children}
      {nodes.map((node) => {
        const Component = nodeTypes[node.type];
        return (
          <div key={node.id} onClick={(event) => onNodeClick(event, node)}>
            <Component data={node.data} id={node.id} selected={node.selected} />
          </div>
        );
      })}
    </div>
  ),
  getSmoothStepPath: () => ["M0 0L1 1", 0, 0],
  useReactFlow: () => ({ fitView: vi.fn(), setCenter: vi.fn() }),
}));

import { companyPageCopy } from "./copy";
import { SupplyChainGraph } from "./supply-chain-graph";
import {
  jobFixture,
  quotaFixture,
  supplyChainGraphCachedFixture,
  supplyChainGraphFixture,
  supplyChainGraphInsufficientFixture,
} from "./test-fixtures";

describe("SupplyChainGraph", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("opens source evidence when a relationship is selected", async () => {
    const user = userEvent.setup();
    const onAskContext = vi.fn();
    renderGraph({ onAskContext });

    await user.click(
      screen.getByRole("button", { name: /Supplier 1 supplies Apple Inc\./i }),
    );

    expect(
      screen.getByRole("heading", { name: "Relationship evidence" }),
    ).toBeVisible();
    expect(screen.getByText(/fixture evidence supports relationship 1/i)).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Open official source" }),
    ).toHaveAttribute("href", expect.stringContaining("sec.gov"));
    await user.click(
      screen.getByRole("button", { name: "Ask EquityLens about this relationship" }),
    );
    expect(onAskContext).toHaveBeenCalledWith(
      expect.objectContaining({
        selection: expect.objectContaining({ kind: "supply_chain_edge" }),
      }),
    );
  });

  it("reveals potential relationships after the user enables them", async () => {
    const user = userEvent.setup();
    renderGraph();

    expect(screen.queryByText("Potential relationship")).toBeNull();
    await user.click(
      screen.getByRole("switch", { name: "Potential relationships" }),
    );
    expect(screen.getAllByText("Potential relationship").length).toBeGreaterThan(0);
  });

  it("opens node details, centers a resolved company, and closes the inspector", async () => {
    const user = userEvent.setup();
    const centerCompany = vi.fn();
    const onAskContext = vi.fn();
    renderGraph({ onAskContext, onCenterCompany: centerCompany });

    await user.click(screen.getByRole("button", { name: /Select Supplier 1 \(/i }));
    expect(screen.getByRole("heading", { name: "Supplier 1" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: /Ask EquityLens: Supplier 1/ }));
    expect(onAskContext).toHaveBeenCalledWith(
      expect.objectContaining({
        selection: expect.objectContaining({ kind: "supply_chain_node" }),
      }),
    );
    await user.click(screen.getByRole("button", { name: "Center on this company" }));
    expect(centerCompany).toHaveBeenCalledWith("SUP1");
    await user.click(screen.getByRole("button", { name: "Close evidence" }));
    expect(screen.queryByRole("heading", { name: "Supplier 1" })).toBeNull();
  });

  it("renders bilingual controls and relationship predicates", () => {
    renderGraph({ copy: companyPageCopy.zh.graph, locale: "zh-CN" });

    expect(screen.getByRole("heading", { name: "AI 产业链图谱" })).toBeVisible();
    expect(screen.getByRole("switch", { name: "潜在线索" })).toBeVisible();
    expect(screen.getAllByText("供应").length).toBeGreaterThan(0);
  });

  it("shows an insufficient-evidence research result", () => {
    renderGraph({ graph: supplyChainGraphInsufficientFixture });

    expect(screen.getByRole("status")).toHaveTextContent(
      "Official evidence supports a limited graph",
    );
    expect(screen.getByText(supplyChainGraphInsufficientFixture.snapshot.thesis)).toBeVisible();
  });

  it("keeps the current snapshot visible during an active refresh", () => {
    renderGraph({ graph: supplyChainGraphFixture });

    expect(screen.getByRole("status")).toHaveTextContent("Collecting official sources");
    expect(screen.getByText(supplyChainGraphFixture.snapshot.thesis)).toBeVisible();
    expect(screen.getByRole("button", { name: /Select Apple Inc\./i })).toBeVisible();
  });

  it("submits initial graph generation and updates quota", async () => {
    const user = userEvent.setup();
    const onQuotaChange = vi.fn();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      Response.json({
        status: "accepted",
        job: { ...jobFixture, result_kind: "supply_chain_graph" },
        job_id: jobFixture.id,
        snapshot_id: null,
        quota: { ...quotaFixture, remaining: 1 },
      }),
    );
    renderGraph({ graph: null, onQuotaChange });

    await user.click(screen.getByRole("button", { name: "Generate graph" }));

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/research/companies/AAPL/supply-chain-graph/sync",
      expect.objectContaining({
        body: JSON.stringify({ force_refresh: false }),
        method: "POST",
      }),
    );
    expect(onQuotaChange).toHaveBeenCalledWith(expect.objectContaining({ remaining: 1 }));
    expect(await screen.findByRole("status")).toHaveTextContent("Queued");
  });

  it("reloads the graph after polling a completed job", async () => {
    vi.useFakeTimers();
    const completedJob = {
      ...jobFixture,
      state: "completed" as const,
      result_kind: "supply_chain_graph" as const,
      graph_snapshot_id: supplyChainGraphCachedFixture.snapshot.id,
    };
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(Response.json(completedJob))
      .mockResolvedValueOnce(Response.json(supplyChainGraphCachedFixture));
    renderGraph({ graph: supplyChainGraphFixture });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      `/api/research/jobs/${supplyChainGraphFixture.refresh_job?.id}`,
      expect.objectContaining({ cache: "no-store" }),
    );
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("evidence=verified%2Cpotential"))).toBe(true);
    expect(screen.queryByText("Collecting official sources")).toBeNull();
  });

  it("keeps polling an active initial job until its first graph is published", async () => {
    vi.useFakeTimers();
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        Response.json({
          status: "active_job",
          job: { ...jobFixture, result_kind: "supply_chain_graph" },
          job_id: jobFixture.id,
          snapshot_id: null,
          quota: { ...quotaFixture, remaining: 1 },
        }),
      )
      .mockResolvedValueOnce(
        Response.json({ code: "GRAPH_NOT_FOUND" }, { status: 404 }),
      )
      .mockResolvedValueOnce(Response.json(supplyChainGraphCachedFixture));
    renderGraph({ graph: null });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Generate graph" }));
      await Promise.resolve();
    });
    await act(() => vi.advanceTimersByTimeAsync(2_000));
    await act(() => vi.advanceTimersByTimeAsync(2_000));

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(
      screen.getByText(supplyChainGraphCachedFixture.snapshot.thesis),
    ).toBeVisible();
  });

  it("shows retry for eligible failures and retries the job", async () => {
    const user = userEvent.setup();
    const failedGraph = structuredClone(supplyChainGraphFixture);
    failedGraph.refresh_job = {
      ...failedGraph.refresh_job!,
      state: "failed",
      retry_eligible: true,
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      Response.json({ ...failedGraph.refresh_job, state: "queued" }),
    );
    renderGraph({ graph: failedGraph });

    await user.click(screen.getByRole("button", { name: "Retry graph research" }));

    expect(globalThis.fetch).toHaveBeenCalledWith(
      `/api/research/jobs/${failedGraph.refresh_job.id}/retry`,
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("keeps a failed initial job retryable and refreshes refunded quota", async () => {
    vi.useFakeTimers();
    const onQuotaChange = vi.fn();
    const failedJob = {
      ...jobFixture,
      state: "failed" as const,
      result_kind: "supply_chain_graph" as const,
      retry_eligible: true,
    };
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        Response.json({
          status: "accepted",
          job: { ...jobFixture, result_kind: "supply_chain_graph" },
          job_id: jobFixture.id,
          snapshot_id: null,
          quota: { ...quotaFixture, used: 1, remaining: 1 },
        }),
      )
      .mockResolvedValueOnce(Response.json(failedJob))
      .mockResolvedValueOnce(
        Response.json({ code: "GRAPH_NOT_FOUND" }, { status: 404 }),
      )
      .mockResolvedValueOnce(
        Response.json({ ...quotaFixture, used: 0, remaining: 2 }),
      );
    renderGraph({ graph: null, onQuotaChange });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Generate graph" }));
      await Promise.resolve();
    });
    await act(() => vi.advanceTimersByTimeAsync(2_000));

    expect(
      screen.getByRole("button", { name: "Retry graph research" }),
    ).toBeVisible();
    expect(onQuotaChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ remaining: 2 }),
    );
  });

  it("reports quota exhaustion and exposes graph/list view controls", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      Response.json({ code: "DAILY_AGENT_LIMIT_REACHED" }, { status: 429 }),
    );
    renderGraph();

    expect(screen.getByRole("button", { name: "Fit graph" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Refresh graph" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Daily graph allowance used");
    await user.click(screen.getByRole("button", { name: "Relationship list" }));
    expect(screen.getByRole("list", { name: "Supply-chain relationships" })).toBeVisible();
  });
});

function renderGraph(
  overrides: Partial<React.ComponentProps<typeof SupplyChainGraph>> = {},
) {
  return render(
    <SupplyChainGraph
      copy={companyPageCopy.en.graph}
      graph={supplyChainGraphCachedFixture}
      locale="en-US"
      symbol="AAPL"
      {...overrides}
    />,
  );
}
