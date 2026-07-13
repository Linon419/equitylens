"use client";

import { useCallback, useEffect, useState } from "react";

import { AnalysisControl } from "./analysis-control";
import { BusinessSummary } from "./business-summary";
import { CitationPanel } from "./citation-panel";
import { CompanyHeader } from "./company-header";
import { companyPageCopy } from "./copy";
import type { CompanyPageCopy } from "./copy";
import { EvidenceFlow } from "./evidence-flow";
import { FinancialTable } from "./financial-table";
import { MarketContext } from "./market-context";
import type { Locale } from "@/lib/i18n";
import {
  parseResearchResponse,
  type Citation,
  type Company,
  type FinancialsResponse,
  type IntelligenceResponse,
  type MarketResponse,
  type QuotaStatus,
} from "@/lib/research/types";

export { companyPageCopy };

type Resources = {
  loading: boolean;
  notFound: boolean;
  company?: Company;
  market?: MarketResponse;
  financials?: FinancialsResponse;
  intelligence?: IntelligenceResponse;
  quota?: QuotaStatus;
  unavailable: string[];
};

export function CompanyPage({
  copy,
  locale,
  symbol,
}: {
  copy: CompanyPageCopy;
  locale: Locale;
  symbol: string;
}) {
  const [resources, setResources] = useState<Resources>({
    loading: true,
    notFound: false,
    unavailable: [],
  });
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const language = locale === "zh-CN" ? "zh" : "en";
    void Promise.allSettled([
      loadResource<Company>("company", `/api/research/companies/${symbol}`, controller.signal),
      loadResource<MarketResponse>("market", `/api/research/companies/${symbol}/market`, controller.signal),
      loadResource<FinancialsResponse>("financials", `/api/research/companies/${symbol}/financials`, controller.signal),
      loadResource<IntelligenceResponse>(
        "intelligence",
        `/api/research/companies/${symbol}/intelligence?locale=${language}`,
        controller.signal,
      ),
      loadResource<QuotaStatus>("quota", "/api/research/agent-quota", controller.signal),
    ]).then(([company, market, financials, intelligence, quota]) => {
      if (controller.signal.aborted) return;
      const notFound =
        company.status === "rejected" &&
        company.reason instanceof ResearchResponseError &&
        company.reason.status === 404;
      const unavailable = [market, financials, intelligence, quota]
        .map((result, index) =>
          result.status === "rejected"
            ? ["market", "financials", "intelligence", "quota"][index]
            : null,
        )
        .filter((value): value is string => value !== null);
      setResources({
        loading: false,
        notFound,
        company: fulfilled(company),
        market: fulfilled(market),
        financials: fulfilled(financials),
        intelligence: fulfilled(intelligence),
        quota: fulfilled(quota),
        unavailable,
      });
    });
    return () => controller.abort();
  }, [locale, symbol]);

  const handleCompleted = useCallback(
    (intelligence: IntelligenceResponse, quota: QuotaStatus) => {
      setResources((current) => ({
        ...current,
        intelligence,
        quota,
        unavailable: current.unavailable.filter(
          (resource) => resource !== "intelligence" && resource !== "quota",
        ),
      }));
    },
    [],
  );

  if (resources.loading) {
    return <main className="company-page-state">{copy.loading}</main>;
  }
  if (resources.notFound) {
    return (
      <main className="company-page-state company-page-state--not-found">
        <span>404 / {symbol}</span>
        <h1>{copy.notFoundTitle}</h1>
        <p>{copy.notFoundDescription}</p>
        <a href={`/${locale}/dashboard`}>{copy.back}</a>
      </main>
    );
  }
  if (!resources.company) {
    return <main className="company-page-state">{copy.primaryUnavailable}</main>;
  }

  const intelligence = resources.intelligence;
  return (
    <main className="company-page">
      <a className="company-page__back" href={`/${locale}/dashboard`}>← {copy.back}</a>
      <CompanyHeader company={resources.company} copy={copy.header} />
      {resources.unavailable.length > 0 ? (
        <p className="company-page__partial">{copy.partialLoad}</p>
      ) : null}

      {resources.market ? (
        <MarketContext copy={copy.market} data={resources.market} locale={locale} />
      ) : (
        <UnavailableSection title={copy.market.title} message={copy.unavailable} />
      )}

      <section className="company-section company-financials">
        <header className="company-section__header">
          <div><p>{copy.financials.eyebrow}</p><h2>{copy.financials.title}</h2></div>
        </header>
        {resources.financials ? (
          <FinancialTable
            data={resources.financials}
            locale={locale === "zh-CN" ? "zh" : "en"}
          />
        ) : <p>{copy.unavailable}</p>}
      </section>

      {intelligence ? (
        <>
          <BusinessSummary
            citations={intelligence.citations}
            claims={intelligence.content.core_businesses}
            copy={copy.business}
            onCitation={setSelectedCitation}
          />
          <EvidenceFlow
            intelligence={intelligence}
            locale={locale === "zh-CN" ? "zh" : "en"}
          />
          <IntelligenceNotes
            copy={copy.insights}
            intelligence={intelligence}
            locale={locale}
          />
        </>
      ) : (
        <section className="company-section company-intelligence-empty">
          <p>{copy.noIntelligence}</p>
        </section>
      )}

      {resources.quota ? (
        <AnalysisControl
          copy={copy.analysis}
          initialQuota={resources.quota}
          locale={locale}
          symbol={symbol}
          onCompleted={handleCompleted}
        />
      ) : <UnavailableSection title={copy.analysis.title} message={copy.unavailable} />}

      {selectedCitation ? (
        <CitationPanel
          citation={selectedCitation}
          copy={{
            title: copy.evidence.sourceDialog,
            open: copy.evidence.openFiling,
            close: copy.evidence.close,
          }}
          onClose={() => setSelectedCitation(null)}
        />
      ) : null}
    </main>
  );
}

function IntelligenceNotes({
  copy,
  intelligence,
  locale,
}: {
  copy: CompanyPageCopy["insights"];
  intelligence: IntelligenceResponse;
  locale: Locale;
}) {
  return (
    <section className="company-section intelligence-notes">
      <div>
        <h2>{copy.dependencies}</h2>
        {intelligence.content.material_dependencies.map((claim) => (
          <article key={claim.claim_id}><h3>{claim.title}</h3><p>{claim.explanation}</p></article>
        ))}
      </div>
      <div>
        <h2>{copy.competition}</h2>
        {intelligence.content.competitors.map((claim) => (
          <article key={claim.claim_id}><h3>{claim.title}</h3><p>{claim.explanation}</p></article>
        ))}
      </div>
      <aside>
        <h2>{copy.quality}</h2>
        <dl>
          <div><dt>{copy.confidence}</dt><dd>{intelligence.overall_confidence ?? "—"}</dd></div>
          <div><dt>{copy.generated}</dt><dd>{formatTimestamp(intelligence.generated_at, locale)}</dd></div>
          <div><dt>{copy.underlying}</dt><dd>{intelligence.filing_type} · {intelligence.filing_date}</dd></div>
        </dl>
        <h3>{copy.sources}</h3>
        <ol>
          {intelligence.citations.map((citation) => (
            <li key={citation.id}>
              <a href={citation.source_url} rel="noopener noreferrer" target="_blank">
                {citation.section} ↗
              </a>
            </li>
          ))}
        </ol>
      </aside>
    </section>
  );
}

function UnavailableSection({ title, message }: { title: string; message: string }) {
  return <section className="company-section company-unavailable"><h2>{title}</h2><p>{message}</p></section>;
}

class ResearchResponseError extends Error {
  constructor(public status: number) {
    super(`Research response failed: ${status}`);
  }
}

type ResourceKind = Parameters<typeof parseResearchResponse>[0];

async function loadResource<T>(
  kind: ResourceKind,
  url: string,
  signal: AbortSignal,
): Promise<T> {
  let response = await fetch(url, { cache: "no-store", signal });
  if (response.status >= 500) {
    await abortableDelay(retryDelay(response), signal);
    response = await fetch(url, { cache: "no-store", signal });
  }
  if (!response.ok) throw new ResearchResponseError(response.status);
  return parseResearchResponse(kind, await response.json()) as T;
}

function retryDelay(response: Response) {
  const seconds = Number(response.headers.get("retry-after"));
  return Number.isFinite(seconds) && seconds > 0 ? Math.min(seconds * 1_000, 5_000) : 500;
}

function abortableDelay(milliseconds: number, signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const timer = window.setTimeout(resolve, milliseconds);
    signal.addEventListener("abort", () => {
      window.clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    }, { once: true });
  });
}

function fulfilled<T>(result: PromiseSettledResult<T>): T | undefined {
  return result.status === "fulfilled" ? result.value : undefined;
}

function formatTimestamp(value: string, locale: Locale) {
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(value));
}
