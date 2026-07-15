import type {
  ChatCitation,
  ChatLocale,
  ChatMessage,
  ChatQuotaStatus,
  ChatSections,
  ChatStreamEvent,
} from "@/lib/chat/types";

const EMPTY_SECTIONS: ChatSections = {
  direct_conclusion: "",
  key_evidence: "",
  risks_and_uncertainties: "",
  sources: "",
};

export interface LiveAnswer {
  assistantMessageId: string | null;
  stage: "route" | "retrieval" | "web" | "compose" | "verify" | null;
  sections: ChatSections;
  citations: ChatCitation[];
}

export interface ChatStreamState {
  messages: ChatMessage[];
  live: LiveAnswer | null;
  quota: ChatQuotaStatus | null;
  streaming: boolean;
  error: { code: string; retryable: boolean; assistantMessageId: string | null } | null;
}

export type ChatStreamAction =
  | { type: "messages"; items: ChatMessage[]; append?: boolean }
  | { type: "quota"; quota: ChatQuotaStatus }
  | { type: "start" }
  | { type: "event"; event: ChatStreamEvent; question?: string; locale: ChatLocale }
  | { type: "transport_error"; code: string }
  | { type: "reset" };

export const INITIAL_STREAM: ChatStreamState = {
  messages: [],
  live: null,
  quota: null,
  streaming: false,
  error: null,
};

export function chatStreamReducer(
  state: ChatStreamState,
  action: ChatStreamAction,
): ChatStreamState {
  if (action.type === "messages") {
    return {
      ...state,
      messages: action.append
        ? uniqueMessages([...state.messages, ...action.items])
        : action.items,
      live: null,
      streaming: false,
    };
  }
  if (action.type === "quota") return { ...state, quota: action.quota };
  if (action.type === "start") {
    return {
      ...state,
      live: {
        assistantMessageId: null,
        stage: null,
        sections: { ...EMPTY_SECTIONS },
        citations: [],
      },
      streaming: true,
      error: null,
    };
  }
  if (action.type === "transport_error") {
    return {
      ...state,
      live: null,
      streaming: false,
      error: { code: action.code, retryable: false, assistantMessageId: null },
    };
  }
  if (action.type === "reset") return { ...INITIAL_STREAM, quota: state.quota };
  return reduceStreamEvent(state, action.event, action.question, action.locale);
}

function reduceStreamEvent(
  state: ChatStreamState,
  event: ChatStreamEvent,
  question: string | undefined,
  locale: ChatLocale,
): ChatStreamState {
  if (event.kind === "accepted") {
    const user = question
      ? makeUserMessage(
          event.payload.user_message_id,
          event.payload.conversation_id,
          question,
          locale,
        )
      : null;
    return {
      ...state,
      messages: user ? uniqueMessages([...state.messages, user]) : state.messages,
      live: {
        assistantMessageId: event.payload.assistant_message_id,
        stage: null,
        sections: { ...EMPTY_SECTIONS },
        citations: [],
      },
      quota: event.payload.quota,
    };
  }
  if (event.kind === "stage") {
    return state.live
      ? { ...state, live: { ...state.live, stage: event.payload.stage } }
      : state;
  }
  if (event.kind === "section") {
    return state.live
      ? {
          ...state,
          live: {
            ...state.live,
            sections: {
              ...state.live.sections,
              [event.payload.section]:
                state.live.sections[event.payload.section] + event.payload.delta,
            },
          },
        }
      : state;
  }
  if (event.kind === "citation") {
    return state.live
      ? {
          ...state,
          live: {
            ...state.live,
            citations: [...state.live.citations, event.payload],
          },
        }
      : state;
  }
  if (event.kind === "complete") {
    const message = { ...event.payload.message, citations: event.payload.citations };
    return {
      ...state,
      messages: uniqueMessages([...state.messages, message]),
      live: null,
      quota: event.payload.quota,
      streaming: false,
      error: null,
    };
  }
  const failed = makeFailedMessage(event, state.messages, locale);
  return {
    ...state,
    messages: uniqueMessages([...state.messages, failed]),
    live: null,
    quota: event.payload.quota,
    streaming: false,
    error: {
      code: event.payload.code,
      retryable: event.payload.retryable,
      assistantMessageId: event.payload.assistant_message_id,
    },
  };
}

function uniqueMessages(messages: ChatMessage[]): ChatMessage[] {
  const byId = new Map(messages.map((message) => [message.id, message]));
  return [...byId.values()].sort((left, right) =>
    left.created_at.localeCompare(right.created_at) || left.id.localeCompare(right.id),
  );
}

function makeUserMessage(
  id: string,
  conversationId: string,
  content: string,
  locale: ChatLocale,
): ChatMessage {
  const now = new Date().toISOString();
  return {
    id,
    conversation_id: conversationId,
    reply_to_message_id: null,
    role: "user",
    state: "completed",
    content,
    locale,
    response_kind: null,
    evidence_coverage: null,
    error_code: null,
    attempt_count: 0,
    created_at: now,
    completed_at: now,
    citations: [],
  };
}

function makeFailedMessage(
  event: Extract<ChatStreamEvent, { kind: "error" }>,
  messages: ChatMessage[],
  locale: ChatLocale,
): ChatMessage {
  const existing = messages.find((item) => item.id === event.payload.assistant_message_id);
  return {
    id: event.payload.assistant_message_id,
    conversation_id: existing?.conversation_id ?? messages.at(-1)?.conversation_id ?? "",
    reply_to_message_id: existing?.reply_to_message_id ?? messages.at(-1)?.id ?? null,
    role: "assistant",
    state: "failed",
    content: "",
    locale,
    response_kind: null,
    evidence_coverage: null,
    error_code: event.payload.code,
    attempt_count: existing?.attempt_count ?? 0,
    created_at: existing?.created_at ?? new Date().toISOString(),
    completed_at: new Date().toISOString(),
    citations: [],
  };
}
