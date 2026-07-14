import { Handle, Position, type NodeProps } from "@xyflow/react";

import type { CompanyPageCopy } from "./copy";
import type { SupplyChainFlowNode } from "./supply-chain-layout";

export interface SupplyChainNodeUi {
  copy: CompanyPageCopy["graph"];
  focus: boolean;
  verifiedNeighborCount: number;
}

export function SupplyChainNode({ data, selected }: NodeProps<SupplyChainFlowNode>) {
  const ui = data.ui as SupplyChainNodeUi;
  const identity = data.symbol ? `${data.label} (${data.symbol})` : data.label;

  return (
    <div
      className={[
        "supply-chain-node",
        `supply-chain-node--${data.layer}`,
        ui.focus ? "is-focus" : "",
        selected ? "is-selected" : "",
      ].filter(Boolean).join(" ")}
    >
      <Handle type="target" position={Position.Left} />
      <button
        aria-label={`${ui.copy.selectNode} ${identity}, ${ui.copy.layers[data.layer]} ${ui.copy.kinds[data.kind]}`}
        type="button"
      >
        <span className="supply-chain-node__topline">
          <span aria-hidden="true" className="supply-chain-node__icon">
            {kindIcon(data.kind)}
          </span>
          <span>{ui.copy.layers[data.layer]}</span>
          <span>{data.confidence}</span>
        </span>
        <strong>{data.label}</strong>
        {data.symbol ? <small>{data.symbol}</small> : null}
        <span className="supply-chain-node__badge">{ui.copy.kinds[data.kind]}</span>
        <span className="supply-chain-node__links">
          {ui.verifiedNeighborCount} {ui.copy.verifiedNeighbors}
        </span>
      </button>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

function kindIcon(kind: SupplyChainFlowNode["data"]["kind"]) {
  return { company: "◆", business: "▰", product: "●", category: "⬡" }[kind];
}
