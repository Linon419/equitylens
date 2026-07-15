"use client";

import { useEffect, useState } from "react";

import type { ChatReadiness, ChatReadinessResource } from "@/lib/chat/types";
import type { IngestionJob } from "@/lib/research/types";
import type { CompanyChatCopy } from "../copy";

type ReadinessAction = "company_analysis" | "filing_index" | "supply_chain_graph";
type IndexResponse = {
  status: "accepted" | "active_job" | "ready";
  job: IngestionJob | null;
  filing_id: string | null;
};

export function ReadinessPanel({
  copy,
  onNavigate,
  onRefresh,
  readiness,
  symbol,
}: {
  copy: CompanyChatCopy;
  onNavigate: (action: Exclude<ReadinessAction, "filing_index">) => void;
  onRefresh: () => void;
  readiness: ChatReadiness;
  symbol: string;
}) {
  const [indexJob, setIndexJob] = useState<IngestionJob | null>(null);
  const [preparing, setPreparing] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!indexJob || ["completed", "failed"].includes(indexJob.state)) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        const response = await fetch(`/api/research/jobs/${indexJob.id}`, {
          cache: "no-store",
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("filing index status failed");
        const next = await response.json() as IngestionJob;
        setIndexJob(next);
        if (next.state === "completed") onRefresh();
        if (next.state === "failed") setFailed(true);
      } catch (error) {
        if (!(error instanceof DOMException && error.name === "AbortError")) {
          setFailed(true);
        }
      }
    }, 2_000);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [indexJob, onRefresh]);

  async function prepareIndex() {
    setPreparing(true);
    setFailed(false);
    try {
      const response = await fetch(`/api/research/companies/${symbol}/chat-index/sync`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: "{}",
      });
      if (!response.ok) throw new Error("filing index submission failed");
      const result = await response.json() as IndexResponse;
      setIndexJob(result.job);
      if (result.status === "ready") onRefresh();
    } catch {
      setFailed(true);
    } finally {
      setPreparing(false);
    }
  }

  const rows: Array<[string, ChatReadinessResource]> = [
    [copy.readiness.resources.intelligence, readiness.intelligence],
    [copy.readiness.resources.filingText, readiness.filing_text],
    [copy.readiness.resources.filingIndex, effectiveIndex(readiness.filing_index, indexJob, failed)],
    [copy.readiness.resources.graph, readiness.supply_chain_graph],
    [copy.readiness.resources.web, readiness.web_recency],
  ];

  return (
    <section className="chat-readiness" aria-label={copy.readiness.title}>
      <header>
        <h3>{copy.readiness.title}</h3>
        <span>{rows.filter(([, resource]) => resource.state === "ready").length}/5</span>
      </header>
      <ul>
        {rows.map(([label, resource]) => (
          <li key={label}>
            <span>{label}</span>
            <strong className={`is-${resource.state}`}>
              {copy.readiness.states[resource.state]}
            </strong>
            {resource.action === "filing_index" ? (
              <button disabled={preparing} type="button" onClick={() => void prepareIndex()}>
                {copy.readiness.prepareIndex}
              </button>
            ) : null}
            {resource.action === "company_analysis" ? (
              <button type="button" onClick={() => onNavigate("company_analysis")}>
                {copy.readiness.startAnalysis}
              </button>
            ) : null}
            {resource.action === "supply_chain_graph" ? (
              <button type="button" onClick={() => onNavigate("supply_chain_graph")}>
                {copy.readiness.generateGraph}
              </button>
            ) : null}
          </li>
        ))}
      </ul>
      <p>{copy.readiness.zeroQuota}</p>
    </section>
  );
}

function effectiveIndex(
  resource: ChatReadinessResource,
  job: IngestionJob | null,
  failed: boolean,
): ChatReadinessResource {
  if (failed || job?.state === "failed") return { state: "failed", action: "filing_index" };
  if (job && job.state !== "completed") return { state: "running", action: null };
  return resource;
}
