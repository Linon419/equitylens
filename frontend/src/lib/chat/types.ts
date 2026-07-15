export type ChatLocale = "en-US" | "zh-CN";
export type EvidenceCoverage = "complete" | "partial" | "insufficient";

export interface ChatQuotaStatus {
  limit: number;
  used: number;
  remaining: number;
  resets_at: string;
}

export interface ChatCitation {
  id: string;
  ordinal: number;
  source_kind: "filing" | "financial" | "intelligence" | "graph" | "web";
  source_id: string | null;
  title: string;
  source_url: string;
  source_anchor: string | null;
  excerpt: string;
  published_at: string | null;
  retrieved_at: string;
  source_tier: "primary" | "trusted_secondary" | "derived";
  verification: "verified" | "supporting";
}

export interface ChatMessage {
  id: string;
  conversation_id: string;
  reply_to_message_id: string | null;
  role: "user" | "assistant";
  state: "pending" | "planning" | "completed" | "failed";
  content: string;
  locale: ChatLocale;
  evidence_coverage: EvidenceCoverage | null;
  error_code: string | null;
  attempt_count: number;
  created_at: string;
  completed_at: string | null;
  citations: ChatCitation[];
}

export interface AcceptedPayload {
  user_message_id: string;
  assistant_message_id: string;
  conversation_id: string;
  quota: ChatQuotaStatus;
}

export interface StagePayload {
  stage: "retrieval" | "web" | "compose" | "verify";
  status_key: string;
}

export interface SectionPayload {
  section:
    | "direct_conclusion"
    | "key_evidence"
    | "risks_and_uncertainties"
    | "sources";
  delta: string;
}

export interface CompletePayload {
  message: ChatMessage;
  citations: ChatCitation[];
  evidence_coverage: EvidenceCoverage;
  quota: ChatQuotaStatus;
}

export interface ErrorPayload {
  code: string;
  retryable: boolean;
  assistant_message_id: string;
  quota: ChatQuotaStatus;
}

export type ChatStreamEvent =
  | { id: number; kind: "accepted"; payload: AcceptedPayload }
  | { id: number; kind: "stage"; payload: StagePayload }
  | { id: number; kind: "section"; payload: SectionPayload }
  | { id: number; kind: "citation"; payload: ChatCitation }
  | { id: number; kind: "complete"; payload: CompletePayload }
  | { id: number; kind: "error"; payload: ErrorPayload };

export type ChatEventKind = ChatStreamEvent["kind"];
