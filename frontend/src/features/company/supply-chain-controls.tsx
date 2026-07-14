import { useReactFlow } from "@xyflow/react";

import type { CompanyPageCopy } from "./copy";
import { isTerminalGraphJob } from "./use-supply-chain-research";
import type {
  IngestionJob,
  JobStatus,
  SupplyChainGraphResponse,
} from "@/lib/research/types";

export function GraphPrimaryAction({
  copy,
  graph,
  onGenerate,
  onRefresh,
  pending,
}: {
  copy: CompanyPageCopy["graph"];
  graph: SupplyChainGraphResponse | null;
  onGenerate: () => void;
  onRefresh: () => void;
  pending: boolean;
}) {
  return (
    <button className="supply-chain-primary-action" disabled={pending} onClick={graph ? onRefresh : onGenerate} type="button">
      {pending ? copy.pending : graph ? copy.refresh : copy.generate}
    </button>
  );
}

export function GraphViewportAction({ copy }: { copy: CompanyPageCopy["graph"] }) {
  const { fitView } = useReactFlow();
  return <button className="supply-chain-fit" onClick={() => void fitView({ duration: 320, padding: 0.15 })} type="button">{copy.fit}</button>;
}

export function GraphJobStatus({
  copy,
  job,
  stale,
}: {
  copy: CompanyPageCopy["graph"];
  job: IngestionJob;
  stale: boolean;
}) {
  return (
    <div className={`supply-chain-job is-${job.state}`} role="status">
      <span className="supply-chain-job__pulse" aria-hidden="true" />
      <strong>{copy.stages[job.state]}</strong>
      {stale && !isTerminalGraphJob(job.state) ? <span>{copy.refreshing}</span> : null}
      {!isTerminalGraphJob(job.state) ? <progress max={10} value={jobProgress(job.state)} /> : null}
    </div>
  );
}

function jobProgress(state: JobStatus) {
  const stages: JobStatus[] = ["queued", "downloading", "parsing", "analyzing", "collecting", "extracting", "resolving", "verifying", "localizing", "completed"];
  return Math.max(stages.indexOf(state) + 1, 1);
}
