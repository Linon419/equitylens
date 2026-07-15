import type {
  AcceptedPayload,
  ChatCitation,
  ChatEventKind,
  ChatMessage,
  ChatQuotaStatus,
  ChatStreamEvent,
  CompletePayload,
  ErrorPayload,
  EvidenceCoverage,
  SectionPayload,
  StagePayload,
} from "./types";

const EVENT_KINDS = new Set<ChatEventKind>([
  "accepted",
  "stage",
  "section",
  "citation",
  "complete",
  "error",
]);
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export async function* parseChatEventStream(
  stream: ReadableStream<Uint8Array>,
  signal?: AbortSignal,
): AsyncGenerator<ChatStreamEvent> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let lastId = 0;
  const abort = () => {
    void reader.cancel(signal?.reason).catch(() => undefined);
  };
  signal?.addEventListener("abort", abort, { once: true });
  try {
    while (true) {
      throwWhenAborted(signal);
      const { value, done } = await reader.read();
      throwWhenAborted(signal);
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      while (true) {
        const boundary = frameBoundary(buffer);
        if (boundary === null) break;
        const frame = buffer.slice(0, boundary.index);
        buffer = buffer.slice(boundary.index + boundary.length);
        const event = parseFrame(frame, lastId);
        if (event !== null) {
          lastId = event.id;
          yield event;
        }
      }
    }
    buffer += decoder.decode();
    while (true) {
      const boundary = frameBoundary(buffer);
      if (boundary === null) break;
      const frame = buffer.slice(0, boundary.index);
      buffer = buffer.slice(boundary.index + boundary.length);
      const event = parseFrame(frame, lastId);
      if (event !== null) {
        lastId = event.id;
        yield event;
      }
    }
    if (hasIncompleteFrame(buffer)) throw new Error("Incomplete SSE frame");
  } finally {
    signal?.removeEventListener("abort", abort);
    reader.releaseLock();
  }
}

function parseFrame(frame: string, lastId: number): ChatStreamEvent | null {
  let rawId: string | undefined;
  let rawKind: string | undefined;
  const data: string[] = [];
  for (const line of frame.split(/\r\n|\r|\n/)) {
    if (!line || line.startsWith(":")) continue;
    const separator = line.indexOf(":");
    const field = separator < 0 ? line : line.slice(0, separator);
    let value = separator < 0 ? "" : line.slice(separator + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "id") rawId = value;
    if (field === "event") rawKind = value;
    if (field === "data") data.push(value);
  }
  if (rawId === undefined && rawKind === undefined && data.length === 0) return null;
  const id = Number(rawId);
  if (!Number.isSafeInteger(id) || id <= lastId) {
    throw new Error("SSE event IDs must be positive and monotonic");
  }
  if (!EVENT_KINDS.has(rawKind as ChatEventKind)) {
    throw new Error(`Unknown chat event: ${rawKind ?? "missing"}`);
  }
  if (data.length === 0) throw new Error("Missing SSE data");
  let payload: unknown;
  try {
    payload = JSON.parse(data.join("\n"));
  } catch {
    throw new Error("Invalid SSE JSON");
  }
  return validatedEvent(id, rawKind as ChatEventKind, payload);
}

function validatedEvent(
  id: number,
  kind: ChatEventKind,
  payload: unknown,
): ChatStreamEvent {
  switch (kind) {
    case "accepted":
      assertAccepted(payload);
      return { id, kind, payload };
    case "stage":
      assertStage(payload);
      return { id, kind, payload };
    case "section":
      assertSection(payload);
      return { id, kind, payload };
    case "citation":
      assertCitation(payload);
      return { id, kind, payload };
    case "complete":
      assertComplete(payload);
      return { id, kind, payload };
    case "error":
      assertError(payload);
      return { id, kind, payload };
  }
}

function assertAccepted(value: unknown): asserts value is AcceptedPayload {
  const item = record(value, "accepted");
  if (
    !uuid(item.user_message_id) ||
    !uuid(item.assistant_message_id) ||
    !uuid(item.conversation_id) ||
    !quota(item.quota)
  ) {
    throw new Error("Invalid accepted payload");
  }
}

function assertStage(value: unknown): asserts value is StagePayload {
  const item = record(value, "stage");
  if (
    !oneOf(item.stage, ["retrieval", "web", "compose", "verify"]) ||
    !text(item.status_key)
  ) {
    throw new Error("Invalid stage payload");
  }
}

function assertSection(value: unknown): asserts value is SectionPayload {
  const item = record(value, "section");
  if (
    !oneOf(item.section, [
      "direct_conclusion",
      "key_evidence",
      "risks_and_uncertainties",
      "sources",
    ]) ||
    typeof item.delta !== "string"
  ) {
    throw new Error("Invalid section payload");
  }
}

function assertCitation(value: unknown): asserts value is ChatCitation {
  const item = record(value, "citation");
  if (
    !uuid(item.id) ||
    !integer(item.ordinal) ||
    !oneOf(item.source_kind, [
      "filing",
      "financial",
      "intelligence",
      "graph",
      "web",
    ]) ||
    !nullableText(item.source_id) ||
    !text(item.title) ||
    !httpsUrl(item.source_url) ||
    !nullableText(item.source_anchor) ||
    !text(item.excerpt) ||
    !nullableText(item.published_at) ||
    !text(item.retrieved_at) ||
    !oneOf(item.source_tier, ["primary", "trusted_secondary", "derived"]) ||
    !oneOf(item.verification, ["verified", "supporting"])
  ) {
    throw new Error("Invalid citation payload");
  }
}

function assertComplete(value: unknown): asserts value is CompletePayload {
  const item = record(value, "complete");
  if (!message(item.message) || !citationList(item.citations)) {
    throw new Error("Invalid complete payload");
  }
  if (!coverage(item.evidence_coverage) || !quota(item.quota)) {
    throw new Error("Invalid complete payload");
  }
}

function assertError(value: unknown): asserts value is ErrorPayload {
  const item = record(value, "error");
  if (
    !text(item.code) ||
    typeof item.retryable !== "boolean" ||
    !uuid(item.assistant_message_id) ||
    !quota(item.quota)
  ) {
    throw new Error("Invalid error payload");
  }
}

function message(value: unknown): value is ChatMessage {
  if (!isRecord(value)) return false;
  return (
    uuid(value.id) &&
    uuid(value.conversation_id) &&
    (value.reply_to_message_id === null || uuid(value.reply_to_message_id)) &&
    oneOf(value.role, ["user", "assistant"]) &&
    oneOf(value.state, ["pending", "planning", "completed", "failed"]) &&
    typeof value.content === "string" &&
    oneOf(value.locale, ["en-US", "zh-CN"]) &&
    (value.evidence_coverage === null || coverage(value.evidence_coverage)) &&
    nullableText(value.error_code) &&
    integer(value.attempt_count) &&
    text(value.created_at) &&
    nullableText(value.completed_at) &&
    citationList(value.citations)
  );
}

function quota(value: unknown): value is ChatQuotaStatus {
  if (!isRecord(value)) return false;
  return (
    integer(value.limit) &&
    integer(value.used) &&
    integer(value.remaining) &&
    text(value.resets_at)
  );
}

function citationList(value: unknown): value is ChatCitation[] {
  if (!Array.isArray(value)) return false;
  try {
    value.forEach(assertCitation);
    return true;
  } catch {
    return false;
  }
}

function coverage(value: unknown): value is EvidenceCoverage {
  return oneOf(value, ["complete", "partial", "insufficient"]);
}

function record(value: unknown, label: string): Record<string, unknown> {
  if (!isRecord(value)) throw new Error(`Invalid ${label} payload`);
  return value;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function oneOf<T extends string>(value: unknown, allowed: readonly T[]): value is T {
  return typeof value === "string" && allowed.includes(value as T);
}

function text(value: unknown): value is string {
  return typeof value === "string" && value.length > 0;
}

function nullableText(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function integer(value: unknown): value is number {
  return Number.isInteger(value) && (value as number) >= 0;
}

function uuid(value: unknown): value is string {
  return typeof value === "string" && UUID.test(value);
}

function httpsUrl(value: unknown): value is string {
  return typeof value === "string" && value.startsWith("https://");
}

function frameBoundary(value: string): { index: number; length: number } | null {
  const matches = ["\r\n\r\n", "\n\n", "\r\r"]
    .map((delimiter) => ({ index: value.indexOf(delimiter), length: delimiter.length }))
    .filter(({ index }) => index >= 0)
    .sort((left, right) => left.index - right.index || right.length - left.length);
  return matches[0] ?? null;
}

function hasIncompleteFrame(value: string): boolean {
  return value
    .split(/\r\n|\r|\n/)
    .some((line) => line.trim().length > 0 && !line.startsWith(":"));
}

function throwWhenAborted(signal?: AbortSignal): void {
  if (signal?.aborted) throw new DOMException("Chat stream aborted", "AbortError");
}
