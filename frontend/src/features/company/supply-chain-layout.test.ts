import { MarkerType, Position } from "@xyflow/react";
import { describe, expect, it } from "vitest";

import type { SupplyChainGraphNode } from "@/lib/research/types";

import { layoutSupplyChainGraph } from "./supply-chain-layout";
import { supplyChainGraphFixture } from "./test-fixtures";

describe("layoutSupplyChainGraph", () => {
  it("places stable layers in left-to-right columns", () => {
    const first = layoutSupplyChainGraph(
      supplyChainGraphFixture.nodes,
      supplyChainGraphFixture.edges,
    );
    const second = layoutSupplyChainGraph(
      [...supplyChainGraphFixture.nodes].reverse(),
      [...supplyChainGraphFixture.edges].reverse(),
    );

    expect(first).toEqual(second);
    expect(xOf(first.nodes, "upstream")).toBeLessThan(xOf(first.nodes, "core"));
    expect(xOf(first.nodes, "core")).toBeLessThan(
      xOf(first.nodes, "downstream"),
    );
  });

  it("centers the focal company and keeps all positions unique", () => {
    const result = layoutSupplyChainGraph(
      supplyChainGraphFixture.nodes,
      supplyChainGraphFixture.edges,
    );
    const focus = result.nodes.find(
      (node) => node.data.node_key === "company:0000320193",
    );
    const positions = result.nodes.map(
      (node) => `${node.position.x}:${node.position.y}`,
    );

    expect(focus?.position.y).toBe(0);
    expect(new Set(positions).size).toBe(result.nodes.length);
  });

  it("caps the canvas at forty nodes and removes orphan edges", () => {
    const extraNodes = Array.from({ length: 20 }, (_, index) =>
      node(`extra:${index}`, "downstream", 100 + index),
    );
    const result = layoutSupplyChainGraph(
      [...supplyChainGraphFixture.nodes, ...extraNodes],
      supplyChainGraphFixture.edges,
    );
    const nodeIds = new Set(result.nodes.map((item) => item.id));

    expect(result.nodes).toHaveLength(40);
    expect(
      result.edges.every(
        (edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target),
      ),
    ).toBe(true);
  });

  it("uses directional handles and evidence-specific edge styles", () => {
    const result = layoutSupplyChainGraph(
      supplyChainGraphFixture.nodes,
      supplyChainGraphFixture.edges,
    );
    const potential = result.edges.find(
      (edge) => edge.data?.evidence_status === "potential",
    );

    expect(result.nodes.every((item) => item.sourcePosition === Position.Right)).toBe(
      true,
    );
    expect(result.nodes.every((item) => item.targetPosition === Position.Left)).toBe(
      true,
    );
    expect(potential?.style?.strokeDasharray).toBe("7 6");
    expect(potential?.markerEnd).toMatchObject({ type: MarkerType.ArrowClosed });
  });

  it("handles an empty graph and same-rank tie breaks", () => {
    expect(layoutSupplyChainGraph([], [])).toEqual({ nodes: [], edges: [] });
    const nodes = [node("business:z", "core", 1), node("business:a", "core", 1)];

    const result = layoutSupplyChainGraph(nodes, []);

    expect(result.nodes.map((item) => item.data.node_key)).toEqual([
      "business:a",
      "business:z",
    ]);
  });
});

function xOf(
  nodes: ReturnType<typeof layoutSupplyChainGraph>["nodes"],
  layer: SupplyChainGraphNode["layer"],
) {
  const found = nodes.find((node) => node.data.layer === layer);
  if (!found) throw new Error(`missing ${layer}`);
  return found.position.x;
}

function node(
  key: string,
  layer: SupplyChainGraphNode["layer"],
  rank: number,
): SupplyChainGraphNode {
  return {
    id: key,
    node_key: key,
    kind: "business",
    layer,
    label: key,
    description: `${key} description`,
    symbol: null,
    cik: null,
    importance: 0.5,
    confidence: "Medium",
    rank,
  };
}
