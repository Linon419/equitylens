import { useCallback, useEffect, useState } from "react";

import type { Locale } from "@/lib/i18n";
import {
  parseResearchResponse,
  type GraphSyncResponse,
  type IngestionJob,
  type JobStatus,
  type QuotaStatus,
  type SupplyChainGraphResponse,
} from "@/lib/research/types";

const POLL_INTERVAL_MS = 2_000;
const GRAPH_EVIDENCE = "verified,potential";
type PollMode = "job" | "graph" | null;

class GraphNotFoundError extends Error {}

export function useSupplyChainResearch({
  initialGraph,
  initialQuota,
  locale,
  onQuotaChange,
  symbol,
}: {
  initialGraph: SupplyChainGraphResponse | null;
  initialQuota?: QuotaStatus;
  locale: Locale;
  onQuotaChange?: (quota: QuotaStatus) => void;
  symbol: string;
}) {
  const [graph, setGraph] = useState(initialGraph);
  const [quota, setQuota] = useState(initialGraph?.quota ?? initialQuota ?? null);
  const [job, setJob] = useState<IngestionJob | null>(initialGraph?.refresh_job ?? null);
  const [pollMode, setPollMode] = useState<PollMode>(initialGraph?.refresh_job ? "job" : null);
  const [pollVersion, setPollVersion] = useState(0);
  const [pending, setPending] = useState(false);
  const [requestError, setRequestError] = useState(false);
  const [limitReached, setLimitReached] = useState(false);
  const language = locale === "zh-CN" ? "zh" : "en";

  const updateQuota = useCallback((nextQuota: QuotaStatus) => {
    setQuota(nextQuota);
    onQuotaChange?.(nextQuota);
  }, [onQuotaChange]);

  const reloadGraph = useCallback(async (signal?: AbortSignal) => {
    const params = new URLSearchParams({ locale: language, evidence: GRAPH_EVIDENCE });
    const response = await fetch(
      `/api/research/companies/${symbol}/supply-chain-graph?${params}`,
      { cache: "no-store", signal },
    );
    if (response.status === 404) throw new GraphNotFoundError();
    if (!response.ok) throw new Error("graph reload failed");
    const next = parseResearchResponse("supplyChainGraph", await response.json());
    setGraph(next);
    updateQuota(next.quota);
    return next;
  }, [language, symbol, updateQuota]);

  const reloadQuota = useCallback(async (signal?: AbortSignal) => {
    const response = await fetch("/api/research/agent-quota", {
      cache: "no-store",
      signal,
    });
    if (!response.ok) throw new Error("quota reload failed");
    const next = parseResearchResponse("quota", await response.json());
    updateQuota(next);
    return next;
  }, [updateQuota]);

  useEffect(() => {
    if (!pollMode) return;
    if (pollMode === "job" && (!job || isTerminalGraphJob(job.state))) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        if (pollMode === "graph") {
          const previousSnapshot = graph?.snapshot.id;
          let nextGraph: SupplyChainGraphResponse;
          try {
            nextGraph = await reloadGraph(controller.signal);
          } catch (error) {
            if (error instanceof GraphNotFoundError) {
              setPollVersion((current) => current + 1);
              return;
            }
            throw error;
          }
          if (nextGraph.snapshot.id !== previousSnapshot || !nextGraph.refresh_job) {
            setJob(nextGraph.refresh_job);
            setPollMode(nextGraph.refresh_job ? "job" : null);
          } else {
            setPollVersion((current) => current + 1);
          }
          return;
        }
        const response = await fetch(`/api/research/jobs/${job!.id}`, {
          cache: "no-store",
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("job poll failed");
        const nextJob = parseResearchResponse("job", await response.json());
        if (nextJob.state === "completed" && nextJob.graph_snapshot_id) {
          await reloadGraph(controller.signal);
          setJob(null);
          setPollMode(null);
        } else if (nextJob.state === "failed") {
          try {
            await reloadGraph(controller.signal);
          } catch (error) {
            if (isAbortError(error)) throw error;
            try {
              await reloadQuota(controller.signal);
            } catch (quotaError) {
              if (isAbortError(quotaError)) throw quotaError;
              setRequestError(true);
            }
          }
          setJob(nextJob);
          setPollMode(null);
        } else {
          setJob(nextJob);
        }
      } catch (error) {
        if (isAbortError(error)) return;
        setRequestError(true);
        setPollMode(null);
      }
    }, POLL_INTERVAL_MS);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [graph?.snapshot.id, job, pollMode, pollVersion, reloadGraph, reloadQuota]);

  async function startGraph(forceRefresh: boolean) {
    if (pending) return;
    setPending(true);
    setRequestError(false);
    setLimitReached(false);
    try {
      const response = await fetch(`/api/research/companies/${symbol}/supply-chain-graph/sync`, {
        body: JSON.stringify({ force_refresh: forceRefresh }),
        headers: { "content-type": "application/json" },
        method: "POST",
      });
      if (response.status === 429) {
        setLimitReached(true);
        return;
      }
      if (!response.ok) throw new Error("graph sync failed");
      const payload = parseResearchResponse("graphSync", await response.json());
      updateQuota(payload.quota);
      await handleSyncResponse(payload);
    } catch {
      setRequestError(true);
    } finally {
      setPending(false);
    }
  }

  async function handleSyncResponse(payload: GraphSyncResponse) {
    if (payload.status === "reused_snapshot") {
      await reloadGraph();
      return;
    }
    setJob(payload.job);
    setPollMode(payload.status === "active_job" ? "graph" : "job");
    setPollVersion((current) => current + 1);
  }

  async function retryGraph() {
    if (!job || pending) return;
    setPending(true);
    setRequestError(false);
    try {
      const response = await fetch(`/api/research/jobs/${job.id}/retry`, { method: "POST" });
      if (!response.ok) throw new Error("graph retry failed");
      setJob(parseResearchResponse("job", await response.json()));
      setPollMode("job");
    } catch {
      setRequestError(true);
    } finally {
      setPending(false);
    }
  }

  return {
    graph,
    job,
    limitReached,
    pending,
    quota,
    requestError,
    retryGraph,
    startGraph,
  };
}

export function isTerminalGraphJob(state: JobStatus) {
  return state === "completed" || state === "failed";
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}
