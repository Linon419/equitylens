import type {
  Company,
  FinancialsResponse,
  IngestionJob,
  IntelligenceResponse,
  MarketResponse,
  QuotaStatus,
  SupplyChainGraphEdge,
  SupplyChainGraphNode,
  SupplyChainGraphResponse,
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
  result_kind: "company_intelligence",
  snapshot_id: null,
  graph_snapshot_id: null,
  provider_run_id: "fake:job",
  created_at: "2026-07-13T15:00:00Z",
  updated_at: "2026-07-13T15:00:00Z",
};

const focusNode: SupplyChainGraphNode = {
  id: "30000000-0000-4000-8000-000000000000",
  node_key: "company:0000320193",
  kind: "company",
  layer: "core",
  label: "Apple Inc.",
  description: "Designs the integrated device, software, and services ecosystem.",
  symbol: "AAPL",
  cik: "0000320193",
  importance: 1,
  confidence: "High",
  rank: 0,
};

const upstreamNodes: SupplyChainGraphNode[] = Array.from(
  { length: 12 },
  (_, index) => ({
    id: `31000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
    node_key: `upstream:${String(index + 1).padStart(2, "0")}`,
    kind: index < 6 ? "company" : "category",
    layer: "upstream",
    label: `Supplier ${index + 1}`,
    description: `Fixture supplier ${index + 1} provides a critical input or manufacturing capability.`,
    symbol: index < 6 ? `SUP${index + 1}` : null,
    cik: null,
    importance: 0.92 - index * 0.025,
    confidence: index % 3 === 0 ? "High" : "Medium",
    rank: index,
  }),
);

const downstreamNodes: SupplyChainGraphNode[] = Array.from(
  { length: 12 },
  (_, index) => ({
    id: `32000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
    node_key: `downstream:${String(index + 1).padStart(2, "0")}`,
    kind: index < 5 ? "company" : "business",
    layer: "downstream",
    label: `Channel ${index + 1}`,
    description: `Fixture channel ${index + 1} reaches a customer segment or distribution market.`,
    symbol: index < 5 ? `BUY${index + 1}` : null,
    cik: null,
    importance: 0.88 - index * 0.025,
    confidence: index % 4 === 0 ? "High" : "Medium",
    rank: index,
  }),
);

function graphEdge(
  node: SupplyChainGraphNode,
  index: number,
): SupplyChainGraphEdge {
  const upstream = node.layer === "upstream";
  const potential = index % 5 === 4;
  return {
    id: `33000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
    edge_key: `${upstream ? node.node_key : focusNode.node_key}|${upstream ? "supplies" : "sells_to"}|${upstream ? focusNode.node_key : node.node_key}`,
    source: upstream ? node.id : focusNode.id,
    target: upstream ? focusNode.id : node.id,
    relationship_type: upstream ? "supplies" : "sells_to",
    evidence_status: potential ? "potential" : "verified",
    confidence: potential ? "Medium" : "High",
    importance: node.importance,
    explanation: upstream
      ? `${node.label} supports a documented Apple input dependency.`
      : `Apple reaches ${node.label} through a documented route to market.`,
    citations: [
      {
        id: `34000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
        source_id: "35000000-0000-4000-8000-000000000001",
        source_key: "sec:0000320193:2025-10-k",
        excerpt: `This fixture evidence supports relationship ${index + 1} with exact source text.`,
        locator: `Item 1, paragraph ${index + 1}`,
        support_role: "primary",
        confidence: potential ? 0.68 : 0.94,
      },
    ],
  };
}

const graphNodes = [...upstreamNodes, focusNode, ...downstreamNodes];
const graphEdges = [...upstreamNodes, ...downstreamNodes].map(graphEdge);
const graphRefreshJob: IngestionJob = {
  ...jobFixture,
  id: "36000000-0000-4000-8000-000000000001",
  state: "collecting",
  current_step: "collecting",
  result_kind: "supply_chain_graph",
  graph_snapshot_id: "37000000-0000-4000-8000-000000000001",
};

export const supplyChainGraphFixture: SupplyChainGraphResponse = {
  snapshot: {
    id: "37000000-0000-4000-8000-000000000001",
    status: "completed",
    symbol: "AAPL",
    model_id: "gpt-5-mini",
    focus_node_key: focusNode.node_key,
    thesis: "Apple coordinates a concentrated component network and global routes to market.",
    evidence_coverage: "complete",
    overall_confidence: "High",
    node_count: graphNodes.length,
    edge_count: graphEdges.length,
    generated_at: "2026-07-14T12:00:00Z",
  },
  nodes: graphNodes,
  edges: graphEdges,
  sources: [
    {
      id: "35000000-0000-4000-8000-000000000001",
      source_id: "sec:2025-10-k",
      source_key: "sec:0000320193:2025-10-k",
      source_type: "sec_filing",
      publisher: "Apple Inc.",
      title: "Apple 2025 Form 10-K",
      canonical_url: "https://www.sec.gov/Archives/edgar/data/320193/aapl-20250927.htm",
      published_at: "2025-10-31",
    },
    {
      id: "35000000-0000-4000-8000-000000000002",
      source_id: "issuer:fy2025-results",
      source_key: "issuer:0000320193:fy2025-results",
      source_type: "official_press_release",
      publisher: "Apple Inc.",
      title: "Apple reports fourth quarter results",
      canonical_url: "https://www.apple.com/newsroom/2025/10/apple-reports-fourth-quarter-results/",
      published_at: "2025-10-30",
    },
  ],
  refresh_job: graphRefreshJob,
  quota: quotaFixture,
};

export const supplyChainGraphCachedFixture: SupplyChainGraphResponse = {
  ...supplyChainGraphFixture,
  refresh_job: null,
};

export const supplyChainGraphInsufficientFixture: SupplyChainGraphResponse = {
  ...supplyChainGraphFixture,
  snapshot: {
    ...supplyChainGraphFixture.snapshot,
    status: "insufficient_evidence",
    evidence_coverage: "insufficient_evidence",
    overall_confidence: "Low",
    thesis: "Available official evidence supports only a partial supply-chain view.",
  },
  edges: supplyChainGraphFixture.edges.filter(
    (edge) => edge.evidence_status === "verified",
  ).slice(0, 4),
  refresh_job: null,
};
