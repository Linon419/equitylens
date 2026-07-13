"use client";

import { useEffect, useState } from "react";

import { analysisCopy } from "./copy";
import type { AnalysisCopy } from "./copy";
import { useSession } from "@/components/session-provider";
import type { Locale } from "@/lib/i18n";
import {
  parseResearchResponse,
  type IngestionJob,
  type IntelligenceResponse,
  type JobStatus,
  type QuotaStatus,
} from "@/lib/research/types";

export { analysisCopy };

export function AnalysisControl({
  copy,
  initialQuota,
  locale,
  onCompleted,
  symbol,
}: {
  copy: AnalysisCopy;
  initialQuota: QuotaStatus;
  locale: Locale;
  onCompleted: (intelligence: IntelligenceResponse, quota: QuotaStatus) => void;
  symbol: string;
}) {
  const { user } = useSession();
  const [quota, setQuota] = useState(initialQuota);
  const [job, setJob] = useState<IngestionJob | null>(null);
  const [activity, setActivity] = useState<"idle" | "retrying">("idle");
  const [pending, setPending] = useState(false);
  const [limitReached, setLimitReached] = useState(false);
  const [requestError, setRequestError] = useState(false);
  const jobId = job?.id;
  const jobState = job?.state;

  useEffect(() => {
    if (!jobId || !jobState || ["completed", "failed"].includes(jobState)) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        const response = await fetch(`/api/research/jobs/${jobId}`, {
          cache: "no-store",
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("job poll failed");
        const nextJob = parseResearchResponse("job", await response.json());
        if (nextJob.state === "completed") {
          await refreshCompletedResearch(symbol, locale, controller.signal, (data, nextQuota) => {
            setQuota(nextQuota);
            onCompleted(data, nextQuota);
          });
        }
        setJob(nextJob);
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setRequestError(true);
      }
    }, 2_000);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [jobId, jobState, locale, onCompleted, symbol]);

  async function startAnalysis() {
    if (pending) return;
    setPending(true);
    setRequestError(false);
    setLimitReached(false);
    try {
      const response = await fetch(`/api/research/companies/${symbol}/sync`, {
        method: "POST",
      });
      if (response.status === 429) {
        setLimitReached(true);
        return;
      }
      if (!response.ok) throw new Error("analysis start failed");
      const payload = parseResearchResponse("sync", await response.json());
      setQuota(payload.quota);
      if (payload.job) setJob(payload.job);
      if (payload.status === "reused_snapshot") {
        await refreshCompletedResearch(symbol, locale, undefined, onCompleted);
      }
    } catch {
      setRequestError(true);
    } finally {
      setPending(false);
    }
  }

  async function retryAnalysis() {
    if (!job || pending) return;
    setActivity("retrying");
    setPending(true);
    try {
      const response = await fetch(`/api/research/jobs/${job.id}/retry`, {
        method: "POST",
      });
      if (!response.ok) throw new Error("analysis retry failed");
      setJob(parseResearchResponse("job", await response.json()));
    } catch {
      setRequestError(true);
    } finally {
      setActivity("idle");
      setPending(false);
    }
  }

  const state: JobStatus | "idle" | "retrying" =
    activity === "retrying" ? "retrying" : (job?.state ?? "idle");
  return (
    <section className="analysis-control">
      <div>
        <p>{copy.eyebrow}</p>
        <h2>{copy.title}</h2>
        <span>{copy.description}</span>
      </div>
      <div className="analysis-control__status">
        <strong>{copy.states[state]}</strong>
        <span>{quota.remaining} {copy.remaining}</span>
        {job ? <progress max={7} value={progressFor(job.state)} /> : null}
      </div>
      {limitReached ? (
        <div className="analysis-control__limit" role="alert">
          <p>{copy.limit}. {copy.reset}: {formatReset(quota.resets_at, locale)}</p>
          {user ? null : (
            <a href={`/${locale}/login?returnTo=${encodeURIComponent(`/${locale}/companies/${symbol}`)}`}>
              {copy.signIn}
            </a>
          )}
        </div>
      ) : null}
      {requestError ? <p role="alert">{copy.failed}</p> : null}
      {job?.state === "failed" && job.retry_eligible ? (
        <button disabled={pending} type="button" onClick={retryAnalysis}>
          {copy.retry}
        </button>
      ) : (
        <button disabled={pending || Boolean(job && !["completed", "failed"].includes(job.state))} type="button" onClick={startAnalysis}>
          {pending ? copy.pending : copy.start}
        </button>
      )}
    </section>
  );
}

async function refreshCompletedResearch(
  symbol: string,
  locale: Locale,
  signal: AbortSignal | undefined,
  complete: (intelligence: IntelligenceResponse, quota: QuotaStatus) => void,
) {
  const language = locale === "zh-CN" ? "zh" : "en";
  const [intelligenceResponse, quotaResponse] = await Promise.all([
    fetch(`/api/research/companies/${symbol}/intelligence?locale=${language}`, {
      cache: "no-store",
      signal,
    }),
    fetch("/api/research/agent-quota", { cache: "no-store", signal }),
  ]);
  if (!intelligenceResponse.ok || !quotaResponse.ok) {
    throw new Error("completed research refresh failed");
  }
  complete(
    parseResearchResponse("intelligence", await intelligenceResponse.json()),
    parseResearchResponse("quota", await quotaResponse.json()),
  );
}

function progressFor(state: JobStatus) {
  return ["queued", "downloading", "parsing", "analyzing", "verifying", "localizing", "completed"].indexOf(state) + 1;
}

function formatReset(value: string, locale: Locale) {
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(value));
}
