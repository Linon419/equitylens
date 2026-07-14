import type { MouseEvent } from "react";

import type { CompanyPageCopy } from "./copy";
import type {
  SupplyChainGraphEdge,
  SupplyChainGraphNode,
  SupplyChainLayer,
} from "@/lib/research/types";

export function SupplyChainRelationshipList({
  className,
  copy,
  edges,
  nodes,
  onSelect,
  selectedId,
}: {
  className: string;
  copy: CompanyPageCopy["graph"];
  edges: SupplyChainGraphEdge[];
  nodes: SupplyChainGraphNode[];
  onSelect: (event: MouseEvent<HTMLButtonElement>, edge: SupplyChainGraphEdge) => void;
  selectedId: string | null;
}) {
  return (
    <ol className={`supply-chain-list ${className}`} aria-label={copy.listLabel}>
      {(["upstream", "core", "downstream"] as SupplyChainLayer[]).map((layer) => {
        const layerEdges = edges.filter((edge) => relationshipLayer(edge, nodes) === layer);
        if (layerEdges.length === 0) return null;
        return (
          <li key={layer} className={`supply-chain-list__group is-${layer}`}>
            <h3>{copy.layers[layer]}</h3>
            <ul>
              {layerEdges.map((edge) => (
                <li key={edge.id}>
                  <button
                    aria-pressed={selectedId === edge.id}
                    className={selectedId === edge.id ? "is-selected" : ""}
                    onClick={(event) => onSelect(event, edge)}
                    type="button"
                  >
                    <RelationshipText copy={copy} edge={edge} nodes={nodes} />
                    <span>{edge.evidence_status === "verified" ? copy.verified : copy.potential}</span>
                  </button>
                </li>
              ))}
            </ul>
          </li>
        );
      })}
    </ol>
  );
}

function RelationshipText({
  copy,
  edge,
  nodes,
}: {
  copy: CompanyPageCopy["graph"];
  edge: SupplyChainGraphEdge;
  nodes: SupplyChainGraphNode[];
}) {
  const source = nodes.find((node) => node.id === edge.source)?.label ?? edge.source;
  const target = nodes.find((node) => node.id === edge.target)?.label ?? edge.target;
  const predicate = copy.predicates[edge.relationship_type as keyof typeof copy.predicates]
    ?? edge.relationship_type.replaceAll("_", " ");
  return <strong><span>{source}</span> <span>{predicate}</span> <span>{target}.</span></strong>;
}

function relationshipLayer(edge: SupplyChainGraphEdge, nodes: SupplyChainGraphNode[]) {
  const source = nodes.find((node) => node.id === edge.source);
  const target = nodes.find((node) => node.id === edge.target);
  return source?.layer === "core" ? target?.layer ?? "core" : source?.layer ?? "core";
}

export function directVerifiedEdges(nodeId: string, edges: SupplyChainGraphEdge[]) {
  return edges.filter((edge) => edge.evidence_status === "verified" && (edge.source === nodeId || edge.target === nodeId));
}

export function verifiedNeighborCounts(nodes: SupplyChainGraphNode[], edges: SupplyChainGraphEdge[]) {
  return new Map(nodes.map((node) => [node.id, directVerifiedEdges(node.id, edges).length]));
}
