import {
  BaseEdge,
  getSmoothStepPath,
  type EdgeProps,
} from "@xyflow/react";

import type { SupplyChainFlowEdge } from "./supply-chain-layout";

export function SupplyChainEdge({
  id,
  markerEnd,
  selected,
  sourceX,
  sourceY,
  sourcePosition,
  style,
  targetX,
  targetY,
  targetPosition,
}: EdgeProps<SupplyChainFlowEdge>) {
  const [path] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    borderRadius: 18,
  });

  return (
    <g className={selected ? "supply-chain-edge-path is-selected" : "supply-chain-edge-path"}>
      {selected ? (
        <BaseEdge
          id={`${id}-halo`}
          path={path}
          style={{ ...style, stroke: "#071b2d", strokeWidth: 7, opacity: 0.28 }}
        />
      ) : null}
      <BaseEdge id={id} markerEnd={markerEnd} path={path} style={style} />
    </g>
  );
}
