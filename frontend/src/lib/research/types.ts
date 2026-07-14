export type ResearchHttpMethod = "GET" | "POST" | "DELETE";

export interface ResearchErrorResponse {
  code: string;
  request_id?: string;
}

export interface CompanySearchItem {
  symbol: string;
  name: string;
  exchange: string | null;
}

export interface CompanySearchResponse {
  items: CompanySearchItem[];
  count: number;
}

export interface WatchlistItem extends CompanySearchItem {
  price: string | null;
  trailing_pe: string | null;
  added_at: string;
}

export interface WatchlistResponse {
  items: WatchlistItem[];
  count: number;
}

export type DataFreshness = "fresh" | "stale" | "missing";
export type JobStatus =
  | "queued"
  | "downloading"
  | "parsing"
  | "analyzing"
  | "collecting"
  | "extracting"
  | "resolving"
  | "verifying"
  | "localizing"
  | "completed"
  | "failed";
export type Confidence = "High" | "Medium" | "Low";
export type EvidenceCoverage =
  | "complete"
  | "partial"
  | "insufficient_evidence";

export interface Company extends CompanySearchItem {
  cik: string;
  sector: string | null;
  industry: string | null;
  description: string | null;
}

export interface MarketMetric {
  value: string | null;
  missing_reason: string | null;
}

export interface MarketResponse {
  symbol: string;
  price: MarketMetric;
  previous_close: MarketMetric;
  price_change: MarketMetric;
  price_change_percent: MarketMetric;
  market_cap: MarketMetric;
  trailing_eps: MarketMetric;
  trailing_pe: MarketMetric;
  forward_pe: MarketMetric;
  currency: string;
  provider: string;
  observed_at: string;
  fetched_at: string;
  freshness: Exclude<DataFreshness, "missing">;
}

export interface FinancialPoint {
  period_key: string;
  value: string;
  unit: string;
  end_date: string;
  accession_number: string;
  source_url: string;
}

export interface FinancialSeries {
  metric_key: string;
  annual: FinancialPoint[];
  ttm: FinancialPoint | null;
  missing_reason: string | null;
}

export interface FinancialsResponse {
  symbol: string;
  series: FinancialSeries[];
  source: "SEC XBRL Company Facts";
  fetched_at: string;
  freshness: Exclude<DataFreshness, "missing">;
}

export interface IntelligenceClaim {
  claim_id: string;
  title: string;
  explanation: string;
  confidence: Confidence;
  citation_ids: string[];
  revenue_share: string | null;
  revenue_period: string | null;
}

export interface Citation {
  id: string;
  filing_type: "10-K";
  filing_date: string;
  section: string;
  source_anchor: string;
  excerpt: string;
  source_url: string;
}

export interface CitationDraft {
  citation_id: string;
  section_id: string;
  excerpt: string;
}

export interface IntelligenceContent {
  locale: "en" | "zh";
  evidence_coverage: EvidenceCoverage;
  overall_confidence: Confidence | null;
  core_businesses: IntelligenceClaim[];
  revenue_engines: IntelligenceClaim[];
  upstream: IntelligenceClaim[];
  company_layer: IntelligenceClaim[];
  downstream: IntelligenceClaim[];
  competitors: IntelligenceClaim[];
  material_dependencies: IntelligenceClaim[];
  citations: CitationDraft[];
}

export interface IntelligenceResponse {
  snapshot_id: string;
  symbol: string;
  filing_type: "10-K";
  filing_date: string;
  filing_url: string;
  evidence_coverage: EvidenceCoverage;
  overall_confidence: Confidence | null;
  model_id: string;
  generated_at: string;
  content: IntelligenceContent;
  citations: Citation[];
}

export interface QuotaStatus {
  limit: number;
  used: number;
  remaining: number;
  resets_at: string;
}

export interface IngestionJob {
  id: string;
  company_symbol: string;
  state: JobStatus;
  current_step: string;
  attempt_count: number;
  retry_eligible: boolean;
  error_code: string | null;
  result_kind: "company_intelligence" | "supply_chain_graph";
  snapshot_id: string | null;
  graph_snapshot_id: string | null;
  provider_run_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface SyncResponse {
  status: "accepted" | "active_job" | "reused_snapshot";
  job: IngestionJob | null;
  snapshot_id: string | null;
  quota: QuotaStatus;
}

export type SupplyChainNodeKind =
  | "company"
  | "business"
  | "product"
  | "category";
export type SupplyChainLayer = "upstream" | "core" | "downstream";
export type SupplyChainEvidenceStatus = "verified" | "potential";

export interface SupplyChainSnapshotSummary {
  id: string;
  status: "completed" | "insufficient_evidence";
  symbol: string;
  model_id: string;
  focus_node_key: string;
  thesis: string;
  evidence_coverage: EvidenceCoverage;
  overall_confidence: Confidence | null;
  node_count: number;
  edge_count: number;
  generated_at: string;
}

export interface SupplyChainGraphNode {
  id: string;
  node_key: string;
  kind: SupplyChainNodeKind;
  layer: SupplyChainLayer;
  label: string;
  description: string;
  symbol: string | null;
  cik: string | null;
  importance: number;
  confidence: Confidence;
  rank: number;
}

export interface SupplyChainCitation {
  id: string;
  source_id: string;
  source_key: string;
  excerpt: string;
  locator: string;
  support_role: "primary" | "corroborating";
  confidence: number;
}

export interface SupplyChainGraphEdge {
  id: string;
  edge_key: string;
  source: string;
  target: string;
  relationship_type: string;
  evidence_status: SupplyChainEvidenceStatus;
  confidence: Confidence;
  importance: number;
  explanation: string;
  citations: SupplyChainCitation[];
}

export interface SupplyChainSource {
  id: string;
  source_id: string;
  source_key: string;
  source_type:
    | "sec_filing"
    | "annual_report"
    | "ir_page"
    | "official_press_release";
  publisher: string;
  title: string;
  canonical_url: string;
  published_at: string | null;
}

export interface SupplyChainGraphResponse {
  snapshot: SupplyChainSnapshotSummary;
  nodes: SupplyChainGraphNode[];
  edges: SupplyChainGraphEdge[];
  sources: SupplyChainSource[];
  refresh_job: IngestionJob | null;
  quota: QuotaStatus;
}

export interface GraphSyncResponse {
  status: "accepted" | "active_job" | "reused_snapshot";
  job: IngestionJob | null;
  job_id: string | null;
  snapshot_id: string | null;
  quota: QuotaStatus;
}

type ResearchResponseMap = {
  company: Company;
  market: MarketResponse;
  financials: FinancialsResponse;
  intelligence: IntelligenceResponse;
  quota: QuotaStatus;
  job: IngestionJob;
  sync: SyncResponse;
  supplyChainGraph: SupplyChainGraphResponse;
  graphSync: GraphSyncResponse;
};

export function parseResearchResponse<K extends keyof ResearchResponseMap>(
  kind: K,
  value: unknown,
): ResearchResponseMap[K] {
  const record = asRecord(value, kind);
  const requiredFields: Record<keyof ResearchResponseMap, string[]> = {
    company: ["symbol", "name", "cik"],
    market: ["symbol", "price", "market_cap", "observed_at", "freshness"],
    financials: ["symbol", "series", "source", "fetched_at"],
    intelligence: ["snapshot_id", "symbol", "content", "citations"],
    quota: ["limit", "used", "remaining", "resets_at"],
    job: ["id", "company_symbol", "state", "current_step"],
    sync: ["status", "quota"],
    supplyChainGraph: ["snapshot", "nodes", "edges", "sources", "quota"],
    graphSync: ["status", "quota"],
  };
  for (const field of requiredFields[kind]) {
    if (!(field in record) || record[field] === undefined) {
      throw new Error(`Invalid ${kind} response: missing ${field}`);
    }
  }
  return record as unknown as ResearchResponseMap[K];
}

function asRecord(value: unknown, kind: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`Invalid ${kind} response`);
  }
  return value as Record<string, unknown>;
}
