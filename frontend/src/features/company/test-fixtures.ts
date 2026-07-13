import type {
  Company,
  FinancialsResponse,
  IngestionJob,
  IntelligenceResponse,
  MarketResponse,
  QuotaStatus,
} from "@/lib/research/types";

export const companyFixture: Company = {
  symbol: "AAPL",
  name: "Apple Inc.",
  exchange: "NASDAQ",
  cik: "0000320193",
  sector: "Technology",
  industry: "Consumer Electronics",
  description: "Apple designs devices, software, and services.",
};

const annual = (values: number[], metric: string) =>
  values.map((value, index) => ({
    period_key: `FY${2022 + index}`,
    value: String(value),
    unit: "USD",
    end_date: `${2022 + index}-09-30`,
    accession_number: `0000320193-${22 + index}-000001`,
    source_url: `https://www.sec.gov/Archives/${metric}-${2022 + index}`,
  }));

export const financialsFixture: FinancialsResponse = {
  symbol: "AAPL",
  source: "SEC XBRL Company Facts" as const,
  fetched_at: "2026-07-13T00:00:00Z",
  freshness: "fresh" as const,
  series: [
    ["revenue", [394_000_000_000, 383_000_000_000, 391_000_000_000, 416_000_000_000], 421_000_000_000],
    ["net_income", [99_000_000_000, 97_000_000_000, 94_000_000_000, 112_000_000_000], 114_000_000_000],
    ["operating_cash_flow", [122_000_000_000, 111_000_000_000, 118_000_000_000, 132_000_000_000], 136_000_000_000],
    ["capital_expenditure", [-10_000_000_000, -11_000_000_000, -9_000_000_000, -12_000_000_000], -12_500_000_000],
    ["free_cash_flow", [112_000_000_000, 100_000_000_000, 109_000_000_000, 120_000_000_000], 123_500_000_000],
  ].map(([metric_key, values, ttm]) => ({
    metric_key: metric_key as string,
    annual: annual(values as number[], metric_key as string),
    ttm: {
      period_key: "TTM",
      value: String(ttm),
      unit: "USD",
      end_date: "2026-06-30",
      accession_number: "0000320193-26-000001",
      source_url: `https://www.sec.gov/Archives/${metric_key}-ttm`,
    },
    missing_reason: null,
  })),
};

export const marketFixture: MarketResponse = {
  symbol: "AAPL",
  price: { value: "212.48", missing_reason: null },
  previous_close: { value: "210.10", missing_reason: null },
  price_change: { value: "2.38", missing_reason: null },
  price_change_percent: { value: "1.13", missing_reason: null },
  market_cap: { value: "3180000000000", missing_reason: null },
  trailing_eps: { value: "6.42", missing_reason: null },
  trailing_pe: { value: "33.10", missing_reason: null },
  forward_pe: { value: null, missing_reason: "provider_missing" },
  currency: "USD",
  provider: "yahoo",
  observed_at: "2026-07-13T14:30:00Z",
  fetched_at: "2026-07-13T14:45:00Z",
  freshness: "stale" as const,
};

export const intelligenceFixture: IntelligenceResponse = {
  snapshot_id: "11111111-1111-4111-8111-111111111111",
  symbol: "AAPL",
  filing_type: "10-K" as const,
  filing_date: "2025-10-31",
  filing_url: "https://www.sec.gov/Archives/aapl-10k.htm",
  evidence_coverage: "partial" as const,
  overall_confidence: "High" as const,
  model_id: "gpt-5-mini",
  generated_at: "2026-07-13T15:00:00Z",
  content: {
    locale: "en" as const,
    evidence_coverage: "partial" as const,
    overall_confidence: "High" as const,
    core_businesses: [
      {
        claim_id: "business-1",
        title: "Devices and services",
        explanation: "Premium devices anchor a recurring services ecosystem.",
        confidence: "High" as const,
        citation_ids: ["citation-2"],
        revenue_share: "78",
        revenue_period: "FY2025",
      },
    ],
    revenue_engines: [],
    upstream: [
      {
        claim_id: "upstream-1",
        title: "Advanced semiconductors",
        explanation: "Apple depends on leading-edge chip manufacturing capacity.",
        confidence: "Medium" as const,
        citation_ids: ["citation-1"],
        revenue_share: null,
        revenue_period: null,
      },
    ],
    company_layer: [
      {
        claim_id: "company-1",
        title: "Integrated product ecosystem",
        explanation: "Hardware, operating systems, and services reinforce retention.",
        confidence: "High" as const,
        citation_ids: ["citation-2"],
        revenue_share: null,
        revenue_period: null,
      },
    ],
    downstream: [
      {
        claim_id: "downstream-1",
        title: "Consumers and enterprises",
        explanation: "Direct and carrier channels reach global end customers.",
        confidence: "Low" as const,
        citation_ids: ["citation-3"],
        revenue_share: null,
        revenue_period: null,
      },
    ],
    competitors: [
      {
        claim_id: "competitor-1",
        title: "Platform competition",
        explanation: "Android and Windows ecosystems compete across devices.",
        confidence: "Medium" as const,
        citation_ids: ["citation-3"],
        revenue_share: null,
        revenue_period: null,
      },
    ],
    material_dependencies: [
      {
        claim_id: "dependency-1",
        title: "Supplier concentration",
        explanation: "Critical manufacturing remains concentrated in Asia.",
        confidence: "High" as const,
        citation_ids: ["citation-1"],
        revenue_share: null,
        revenue_period: null,
      },
    ],
    citations: [],
  },
  citations: [
    {
      id: "citation-1",
      filing_type: "10-K" as const,
      filing_date: "2025-10-31",
      section: "Item 1A. Risk Factors",
      source_anchor: "item-1a",
      excerpt: "Manufacturing and assembly are performed by outsourcing partners primarily located in Asia.",
      source_url: "https://www.sec.gov/Archives/aapl-10k.htm#item-1a",
    },
    {
      id: "citation-2",
      filing_type: "10-K" as const,
      filing_date: "2025-10-31",
      section: "Item 1. Business",
      source_anchor: "item-1",
      excerpt: "The Company designs, manufactures and markets smartphones, personal computers, tablets, wearables and services.",
      source_url: "https://www.sec.gov/Archives/aapl-10k.htm#item-1",
    },
    {
      id: "citation-3",
      filing_type: "10-K" as const,
      filing_date: "2025-10-31",
      section: "Item 7. Management's Discussion",
      source_anchor: "item-7",
      excerpt: "The markets for the Company's products and services are highly competitive.",
      source_url: "https://www.sec.gov/Archives/aapl-10k.htm#item-7",
    },
  ],
};

export const quotaFixture: QuotaStatus = {
  limit: 2,
  used: 0,
  remaining: 2,
  resets_at: "2026-07-14T00:00:00Z",
};

export const jobFixture: IngestionJob = {
  id: "22222222-2222-4222-8222-222222222222",
  company_symbol: "AAPL",
  state: "queued",
  current_step: "queued",
  attempt_count: 0,
  retry_eligible: true,
  error_code: null,
  snapshot_id: null,
  provider_run_id: "fake:job",
  created_at: "2026-07-13T15:00:00Z",
  updated_at: "2026-07-13T15:00:00Z",
};
