import {
  MarkerType,
  Position,
  type Edge,
  type Node,
} from "@xyflow/react";

import type {
  SupplyChainGraphEdge,
  SupplyChainGraphNode,
  SupplyChainLayer,
} from "@/lib/research/types";

const COLUMN_X: Record<SupplyChainLayer, number> = {
  upstream: 0,
  core: 440,
  downstream: 880,
};
const LAYER_ORDER: Record<SupplyChainLayer, number> = {
  upstream: 0,
  core: 1,
  downstream: 2,
};
const ROW_GAP = 132;
const MAX_NODES = 40;
const VERIFIED_COLOR = "#0f766e";
const POTENTIAL_COLOR = "#b7791f";

export type SupplyChainFlowNode = Node<
  SupplyChainGraphNode & Record<string, unknown>,
  "supplyChain"
>;
export type SupplyChainFlowEdge = Edge<
  SupplyChainGraphEdge & Record<string, unknown>,
  "supplyChain"
>;

export interface SupplyChainFlowModel {
  nodes: SupplyChainFlowNode[];
  edges: SupplyChainFlowEdge[];
}

export function layoutSupplyChainGraph(
  inputNodes: SupplyChainGraphNode[],
  inputEdges: SupplyChainGraphEdge[],
): SupplyChainFlowModel {
  const ordered = [...inputNodes].sort(compareNodes).slice(0, MAX_NODES);
  const positions = positionByNodeKey(ordered);
  const nodes = ordered.map<SupplyChainFlowNode>((node) => ({
    id: node.id,
    type: "supplyChain",
    position: positions.get(node.node_key) ?? { x: 0, y: 0 },
    data: { ...node },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    draggable: false,
  }));
  const nodeIds = new Set(nodes.map((node) => node.id));
  const edges = [...inputEdges]
    .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
    .sort((left, right) => left.edge_key.localeCompare(right.edge_key))
    .map(toFlowEdge);
  return { nodes, edges };
}

function compareNodes(
  left: SupplyChainGraphNode,
  right: SupplyChainGraphNode,
) {
  return (
    LAYER_ORDER[left.layer] - LAYER_ORDER[right.layer] ||
    left.rank - right.rank ||
    left.node_key.localeCompare(right.node_key)
  );
}

function positionByNodeKey(nodes: SupplyChainGraphNode[]) {
  const result = new Map<string, { x: number; y: number }>();
  for (const layer of ["upstream", "core", "downstream"] as const) {
    const layerNodes = nodes.filter((node) => node.layer === layer);
    const yPositions = layer === "core"
      ? centeredCorePositions(layerNodes)
      : new Map(
          layerNodes.map((node, index) => [
            node.node_key,
            centeredY(index, layerNodes.length),
          ]),
        );
    layerNodes.forEach((node, index) => {
      result.set(node.node_key, {
        x: COLUMN_X[layer],
        y: yPositions.get(node.node_key) ?? centeredY(index, layerNodes.length),
      });
    });
  }
  return result;
}

function centeredCorePositions(nodes: SupplyChainGraphNode[]) {
  const positions = new Map<string, number>();
  if (nodes.length === 0) return positions;
  const [focus] = [...nodes].sort(
    (left, right) =>
      right.importance - left.importance ||
      left.rank - right.rank ||
      left.node_key.localeCompare(right.node_key),
  );
  positions.set(focus.node_key, 0);
  nodes
    .filter((node) => node.node_key !== focus.node_key)
    .forEach((node, index) => {
      const distance = Math.ceil((index + 1) / 2) * ROW_GAP;
      positions.set(node.node_key, index % 2 === 0 ? -distance : distance);
    });
  return positions;
}

function centeredY(index: number, count: number) {
  return (index - (count - 1) / 2) * ROW_GAP;
}

function toFlowEdge(edge: SupplyChainGraphEdge): SupplyChainFlowEdge {
  const potential = edge.evidence_status === "potential";
  const color = potential ? POTENTIAL_COLOR : VERIFIED_COLOR;
  return {
    id: edge.id,
    type: "supplyChain",
    source: edge.source,
    target: edge.target,
    data: { ...edge },
    ariaLabel: edge.explanation,
    className: potential
      ? "supply-chain-edge supply-chain-edge--potential"
      : "supply-chain-edge supply-chain-edge--verified",
    style: {
      stroke: color,
      strokeWidth: potential ? 1.5 : 2,
      strokeDasharray: potential ? "7 6" : undefined,
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color,
      width: 18,
      height: 18,
    },
  };
}
