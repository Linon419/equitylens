"use client";

import {
  Background,
  Controls,
  MiniMap,
  Panel,
  ReactFlow,
  ReactFlowProvider,
  type EdgeMouseHandler,
  type EdgeTypes,
  type NodeMouseHandler,
  type NodeTypes,
} from "@xyflow/react";
import { useCallback, useMemo, useRef, useState } from "react";

import type { CompanyPageCopy } from "./copy";
import {
  GraphJobStatus,
  GraphPrimaryAction,
  GraphViewportAction,
} from "./supply-chain-controls";
import { SupplyChainEdge } from "./supply-chain-edge";
import { SupplyChainInspector } from "./supply-chain-inspector";
import { SupplyChainLegend } from "./supply-chain-legend";
import { layoutSupplyChainGraph } from "./supply-chain-layout";
import { SupplyChainNode } from "./supply-chain-node";
import {
  directVerifiedEdges,
  SupplyChainRelationshipList,
  verifiedNeighborCounts,
} from "./supply-chain-relationship-list";
import { isTerminalGraphJob, useSupplyChainResearch } from "./use-supply-chain-research";
import type { Locale } from "@/lib/i18n";
import {
  type QuotaStatus,
  type SupplyChainGraphResponse,
} from "@/lib/research/types";

const nodeTypes = { supplyChain: SupplyChainNode } as NodeTypes;
const edgeTypes = { supplyChain: SupplyChainEdge } as EdgeTypes;

type Selection = { type: "node" | "edge"; id: string } | null;

export function SupplyChainGraph({
  copy,
  graph: initialGraph,
  initialQuota,
  locale,
  onCenterCompany,
  onQuotaChange,
  symbol,
  unavailable = false,
}: {
  copy: CompanyPageCopy["graph"];
  graph: SupplyChainGraphResponse | null;
  initialQuota?: QuotaStatus;
  locale: Locale;
  onCenterCompany?: (symbol: string) => void | Promise<void>;
  onQuotaChange?: (quota: QuotaStatus) => void;
  symbol: string;
  unavailable?: boolean;
}) {
  const {
    graph,
    job,
    limitReached,
    pending,
    quota,
    requestError,
    retryGraph,
    startGraph,
  } = useSupplyChainResearch({ initialGraph, initialQuota, locale, onQuotaChange, symbol });
  const [selection, setSelection] = useState<Selection>(null);
  const [showPotential, setShowPotential] = useState(false);
  const [view, setView] = useState<"graph" | "list">(() => defaultView());
  const selectionControl = useRef<HTMLElement | null>(null);

  const visibleEdges = useMemo(
    () => graph?.edges.filter((edge) => showPotential || edge.evidence_status === "verified") ?? [],
    [graph?.edges, showPotential],
  );
  const flow = useMemo(() => {
    if (!graph) return { nodes: [], edges: [] };
    const model = layoutSupplyChainGraph(graph.nodes, visibleEdges);
    const verifiedCounts = verifiedNeighborCounts(graph.nodes, graph.edges);
    return {
      nodes: model.nodes.map((node) => ({
        ...node,
        selected: selection?.type === "node" && selection.id === node.id,
        data: {
          ...node.data,
          ui: {
            copy,
            focus: node.data.node_key === graph.snapshot.focus_node_key,
            verifiedNeighborCount: verifiedCounts.get(node.id) ?? 0,
          },
        },
      })),
      edges: model.edges.map((edge) => ({
        ...edge,
        selected: selection?.type === "edge" && selection.id === edge.id,
      })),
    };
  }, [copy, graph, selection, visibleEdges]);

  const selectedNode = selection?.type === "node"
    ? graph?.nodes.find((node) => node.id === selection.id)
    : undefined;
  const selectedEdge = selection?.type === "edge"
    ? graph?.edges.find((edge) => edge.id === selection.id)
    : undefined;

  const selectNode: NodeMouseHandler = useCallback((event, node) => {
    selectionControl.current = event.target instanceof HTMLElement ? event.target : null;
    setSelection({ type: "node", id: node.id });
  }, []);
  const selectEdge: EdgeMouseHandler = useCallback((event, edge) => {
    selectionControl.current = event.target instanceof HTMLElement ? event.target : null;
    setSelection({ type: "edge", id: edge.id });
  }, []);

  async function centerCompany(nextSymbol: string) {
    if (onCenterCompany) {
      await onCenterCompany(nextSymbol);
      return;
    }
    await fetch(`/api/research/companies/${nextSymbol}/supply-chain-graph/sync`, {
      body: JSON.stringify({ force_refresh: false }),
      headers: { "content-type": "application/json" },
      method: "POST",
    });
    window.location.assign(`/${locale}/companies/${nextSymbol}`);
  }

  function closeInspector() {
    setSelection(null);
    window.setTimeout(() => selectionControl.current?.focus(), 0);
  }

  const displayedJob = job ?? graph?.refresh_job ?? null;
  const active = Boolean(displayedJob && !isTerminalGraphJob(displayedJob.state));

  return (
    <section className="company-section supply-chain-section">
      <header className="supply-chain-section__header">
        <div>
          <p>{copy.eyebrow}</p>
          <h2>{copy.title}</h2>
        </div>
        <GraphPrimaryAction
          copy={copy}
          graph={graph}
          onGenerate={() => void startGraph(false)}
          onRefresh={() => void startGraph(true)}
          pending={pending}
        />
      </header>

      {active || displayedJob?.state === "failed" ? (
        <GraphJobStatus copy={copy} job={displayedJob!} stale={Boolean(graph)} />
      ) : null}
      {graph?.snapshot.status === "insufficient_evidence" ? (
        <div className="supply-chain-result" role="status">
          <strong>{copy.insufficient}</strong><span>{copy.insufficientDescription}</span>
        </div>
      ) : null}
      {limitReached ? <p className="supply-chain-alert" role="alert">{copy.limit}{quota ? `. ${copy.reset}: ${formatReset(quota.resets_at, locale)}` : ""}</p> : null}
      {requestError ? <p className="supply-chain-alert" role="alert">{copy.failed}</p> : null}
      {displayedJob?.state === "failed" && displayedJob.retry_eligible ? (
        <button className="supply-chain-retry" disabled={pending} onClick={() => void retryGraph()} type="button">
          {copy.retry}
        </button>
      ) : null}

      {graph ? (
        <>
          <div className="supply-chain-thesis">
            <p>{copy.thesis}</p><strong>{graph.snapshot.thesis}</strong>
            <dl>
              <div><dt>{copy.coverage}</dt><dd>{graph.snapshot.evidence_coverage}</dd></div>
              <div><dt>{copy.generated}</dt><dd>{formatDate(graph.snapshot.generated_at, locale)}</dd></div>
            </dl>
          </div>
          <div className="supply-chain-toolbar">
            <div role="group" aria-label="Supply-chain view">
              <button aria-pressed={view === "graph"} onClick={() => setView("graph")} type="button">{copy.graphView}</button>
              <button aria-pressed={view === "list"} onClick={() => setView("list")} type="button">{copy.listView}</button>
            </div>
            <label>
              <input
                aria-label={copy.potentialToggle}
                checked={showPotential}
                onChange={(event) => {
                  const checked = event.target.checked;
                  setShowPotential(checked);
                  if (!checked && selection?.type === "edge") {
                    const edge = graph.edges.find((candidate) => candidate.id === selection.id);
                    if (edge?.evidence_status === "potential") setSelection(null);
                  }
                }}
                role="switch"
                type="checkbox"
              />
              <span>{copy.potentialToggle}</span>
            </label>
            {quota ? <span>{quota.remaining} {copy.remaining}</span> : null}
          </div>
          <SupplyChainLegend copy={copy} />
          <div className={selection ? "supply-chain-workspace has-selection" : "supply-chain-workspace"}>
            <div className={view === "graph" ? "supply-chain-canvas" : "supply-chain-canvas is-hidden"}>
              <ReactFlowProvider>
                <ReactFlow
                  attributionPosition="bottom-left"
                  edges={flow.edges}
                  edgeTypes={edgeTypes}
                  elementsSelectable
                  fitView
                  disableKeyboardA11y={false}
                  maxZoom={1.8}
                  minZoom={0.35}
                  nodes={flow.nodes}
                  nodesConnectable={false}
                  nodesDraggable={false}
                  nodeTypes={nodeTypes}
                  onEdgeClick={selectEdge}
                  onNodeClick={selectNode}
                >
                  <Background gap={24} size={1} />
                  <MiniMap pannable zoomable />
                  <Controls showInteractive={false} />
                  <Panel position="top-right"><GraphViewportAction copy={copy} /></Panel>
                </ReactFlow>
              </ReactFlowProvider>
            </div>
            <SupplyChainRelationshipList
              className={view === "list" ? "" : "is-accessible-only"}
              copy={copy}
              edges={visibleEdges}
              nodes={graph.nodes}
              onSelect={(event, edge) => {
                selectionControl.current = event.currentTarget;
                setSelection({ type: "edge", id: edge.id });
              }}
              selectedId={selection?.type === "edge" ? selection.id : null}
            />
            {selectedNode || selectedEdge ? (
              <SupplyChainInspector
                copy={copy}
                directEdges={selectedNode ? directVerifiedEdges(selectedNode.id, graph.edges) : []}
                locale={locale}
                nodes={graph.nodes}
                onCenterCompany={(nextSymbol) => void centerCompany(nextSymbol)}
                onClose={closeInspector}
                selection={selectedNode ? { type: "node", value: selectedNode } : { type: "edge", value: selectedEdge! }}
                sources={graph.sources}
              />
            ) : null}
          </div>
        </>
      ) : (
        <div className="supply-chain-empty">
          <span aria-hidden="true">⌘</span><h3>{copy.emptyTitle}</h3><p>{unavailable ? copy.failed : copy.emptyDescription}</p>
        </div>
      )}
    </section>
  );
}

function defaultView(): "graph" | "list" {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return "graph";
  return window.matchMedia("(max-width: 760px)").matches ? "list" : "graph";
}

function formatDate(value: string, locale: Locale) {
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: "UTC" }).format(new Date(value));
}

function formatReset(value: string, locale: Locale) {
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(new Date(value));
}
