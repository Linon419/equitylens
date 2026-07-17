"use client";

import { useCallback, useEffect, useState, type CSSProperties } from "react";

import { useSession } from "@/components/session-provider";
import { AnalysisControl } from "./analysis-control";
import { BusinessSummary } from "./business-summary";
import { ChatWorkbench } from "./chat/chat-workbench";
import { CitationPanel } from "./citation-panel";
import { CompanyHeader } from "./company-header";
import { companyPageCopy } from "./copy";
import type { CompanyPageCopy } from "./copy";
import { FinancialTable } from "./financial-table";
import { MarketContext } from "./market-context";
import { SupplyChainGraph } from "./supply-chain-graph";
import type { Locale } from "@/lib/i18n";
import type { SelectedChatContext } from "@/lib/chat/types";
import {
  parseResearchResponse,
  type Citation,
  type Company,
  type FinancialsResponse,
  type IntelligenceResponse,
  type MarketResponse,
  type QuotaStatus,
  type SupplyChainGraphResponse,
} from "@/lib/research/types";

export { companyPageCopy };

type Resources = {
  loading: boolean;
  notFound: boolean;
  company?: Company;
  market?: MarketResponse;
  financials?: FinancialsResponse;
  intelligence?: IntelligenceResponse;
  supplyChainGraph?: SupplyChainGraphResponse;
  quota?: QuotaStatus;
  unavailable: string[];
};

export function CompanyPage({
  copy,
  initialCompany,
  locale,
  symbol,
}: {
  copy: CompanyPageCopy;
  initialCompany?: Company;
  locale: Locale;
  symbol: string;
}) {
  const { user } = useSession();
  const [resources, setResources] = useState<Resources>({
    loading: initialCompany === undefined,
    notFound: false,
    company: initialCompany,
    unavailable: [],
  });
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const [chatOpen, setChatOpen] = useState(true);
  const [pendingChatContext, setPendingChatContext] =
    useState<SelectedChatContext | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const language = locale === "zh-CN" ? "zh" : "en";
    if (initialCompany === undefined) {
      void loadResource<Company>(
        "company",
        `/api/research/companies/${symbol}`,
        controller.signal,
      ).then((company) => {
        if (controller.signal.aborted) return;
        setResources((current) => ({ ...current, loading: false, company }));
      }).catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setResources((current) => ({
          ...current,
          loading: false,
          notFound: error instanceof ResearchResponseError && error.status === 404,
        }));
      });
    }

    void loadSecondaryResources(symbol, language, controller.signal).then((secondary) => {
      if (controller.signal.aborted) return;
      setResources((current) => ({ ...current, ...secondary }));
    });
    return () => controller.abort();
  }, [initialCompany, locale, symbol]);

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

  const handleQuotaChange = useCallback((quota: QuotaStatus) => {
    setResources((current) => ({
      ...current,
      quota,
      unavailable: current.unavailable.filter((resource) => resource !== "quota"),
    }));
  }, []);

  const handleAskContext = useCallback((context: SelectedChatContext) => {
    setPendingChatContext(context);
    setChatOpen(true);
  }, []);

  const handleReadinessNavigate = useCallback(
    (action: "company_analysis" | "supply_chain_graph") => {
      setChatOpen(false);
      const selector = action === "company_analysis"
        ? ".analysis-control"
        : ".supply-chain-section";
      window.setTimeout(() => {
        const target = document.querySelector<HTMLElement>(selector);
        if (typeof target?.scrollIntoView === "function") {
          target.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      }, 0);
    },
    [],
  );

  if (resources.loading) {
    return <CompanyLoadingShell copy={copy} locale={locale} symbol={symbol} />;
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
    <main className={`company-page${chatOpen ? " company-page--chat-open" : ""}`}>
      <div className="company-dossier">
      <a className="company-page__back" href={`/${locale}/dashboard`}>← {copy.back}</a>
      <CompanyHeader
        company={resources.company}
        copy={copy.header}
        onOpenChat={() => setChatOpen(true)}
      />
      {resources.unavailable.length > 0 ? (
        <p className="company-page__partial">{copy.partialLoad}</p>
      ) : null}

      {resources.market ? (
        <MarketContext
          copy={copy.market}
          data={resources.market}
          locale={locale}
          onAskContext={handleAskContext}
        />
      ) : (
        <UnavailableSection title={copy.market.title} message={copy.unavailable} />
      )}

      <section className="company-section company-financials">
        <header className="company-section__header">
          <div><p>{copy.financials.eyebrow}</p><h2>{copy.financials.title}</h2></div>
        </header>
        {resources.financials ? (
          <FinancialTable
            askLabel={copy.financials.ask}
            data={resources.financials}
            locale={locale === "zh-CN" ? "zh" : "en"}
            onAskContext={handleAskContext}
          />
        ) : <p>{copy.unavailable}</p>}
      </section>

      {intelligence ? (
        <>
          <BusinessSummary
            citations={intelligence.citations}
            claims={intelligence.content.core_businesses}
            copy={copy.business}
            onAskContext={handleAskContext}
            onCitation={setSelectedCitation}
            snapshotId={intelligence.snapshot_id}
          />
        </>
      ) : (
        <section className="company-section company-intelligence-empty">
          <p>{copy.noIntelligence}</p>
        </section>
      )}

      <SupplyChainGraph
        copy={copy.graph}
        graph={resources.supplyChainGraph ?? null}
        initialQuota={resources.quota}
        locale={locale}
        onAskContext={handleAskContext}
        onQuotaChange={handleQuotaChange}
        symbol={symbol}
        unavailable={resources.unavailable.includes("supplyChainGraph")}
      />

      {intelligence ? (
        <IntelligenceNotes
          copy={copy.insights}
          intelligence={intelligence}
          locale={locale}
        />
      ) : null}

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
      </div>
      <ChatWorkbench
        authenticated={Boolean(user)}
        copy={copy.chat}
        locale={locale}
        onClose={() => setChatOpen(false)}
        onContextConsumed={() => setPendingChatContext(null)}
        onReadinessNavigate={handleReadinessNavigate}
        open={chatOpen}
        pendingContext={pendingChatContext}
        symbol={symbol}
      />
    </main>
  );
}

function CompanyLoadingShell({
  copy,
  locale,
  symbol,
}: {
  copy: CompanyPageCopy;
  locale: Locale;
  symbol: string;
}) {
  return (
    <main aria-busy="true" className="company-page company-page--loading">
      <div className="company-dossier">
        <a className="company-page__back" href={`/${locale}/dashboard`}>← {copy.back}</a>
        <header className="company-header company-header--loading">
          <div className="company-header__identity">
            <p>{copy.header.companyRecord} / DATA LINK</p>
            <div className="company-header__ticker">
              <span>{symbol}</span>
              <span>SEC / MARKET / EVIDENCE</span>
            </div>
            <h1>{symbol}</h1>
            <div className="company-loading-status" role="status">
              <span aria-hidden="true" />
              <p>{copy.loading}</p>
            </div>
          </div>
          <dl aria-hidden="true">
            <div><dt>{copy.header.sector}</dt><dd><span className="company-loading-line" /></dd></div>
            <div><dt>{copy.header.industry}</dt><dd><span className="company-loading-line company-loading-line--short" /></dd></div>
          </dl>
        </header>
        <section aria-hidden="true" className="company-loading-sections">
          {[copy.market.title, copy.financials.title, copy.graph.title].map((title, index) => (
            <article key={title} style={{ "--loading-index": index } as CSSProperties}>
              <p>0{index + 1}</p>
              <h2>{title}</h2>
              <span /><span /><span />
            </article>
          ))}
        </section>
      </div>
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
  constructor(public status: number, public code?: string) {
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
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { code?: unknown } | null;
    const code = typeof payload?.code === "string" ? payload.code : undefined;
    throw new ResearchResponseError(response.status, code);
  }
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

async function loadSecondaryResources(
  symbol: string,
  language: "en" | "zh",
  signal: AbortSignal,
): Promise<Partial<Resources>> {
  const results = await Promise.allSettled([
    loadResource<MarketResponse>("market", `/api/research/companies/${symbol}/market`, signal),
    loadResource<FinancialsResponse>("financials", `/api/research/companies/${symbol}/financials`, signal),
    loadResource<IntelligenceResponse>(
      "intelligence",
      `/api/research/companies/${symbol}/intelligence?locale=${language}`,
      signal,
    ),
    loadResource<SupplyChainGraphResponse>(
      "supplyChainGraph",
      `/api/research/companies/${symbol}/supply-chain-graph?locale=${language}&evidence=verified%2Cpotential`,
      signal,
    ),
    loadResource<QuotaStatus>("quota", "/api/research/agent-quota", signal),
  ]);
  const [market, financials, intelligence, supplyChainGraph, quota] = results;
  const intelligenceMissing = rejectedWithCode(intelligence, "INTELLIGENCE_NOT_FOUND");
  const graphMissing = rejectedWithStatus(supplyChainGraph, 404);
  const unavailable = results
    .map((result, index) => {
      const resource = ["market", "financials", "intelligence", "supplyChainGraph", "quota"][index];
      const expectedEmptyState =
        (resource === "intelligence" && intelligenceMissing)
        || (resource === "supplyChainGraph" && graphMissing);
      return result.status === "rejected" && !expectedEmptyState ? resource : null;
    })
    .filter((value): value is string => value !== null);
  return {
    market: fulfilled(market),
    financials: fulfilled(financials),
    intelligence: fulfilled(intelligence),
    supplyChainGraph: fulfilled(supplyChainGraph),
    quota: fulfilled(quota),
    unavailable,
  };
}

function rejectedWithStatus<T>(result: PromiseSettledResult<T>, status: number) {
  return result.status === "rejected"
    && result.reason instanceof ResearchResponseError
    && result.reason.status === status;
}

function rejectedWithCode<T>(result: PromiseSettledResult<T>, code: string) {
  return result.status === "rejected"
    && result.reason instanceof ResearchResponseError
    && result.reason.code === code;
}

function formatTimestamp(value: string, locale: Locale) {
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(value));
}
