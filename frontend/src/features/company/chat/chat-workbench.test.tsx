import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { companyPageCopy } from "../copy";
import { ChatWorkbench } from "./chat-workbench";

const UUIDS = {
  conversation: "11111111-1111-4111-8111-111111111111",
  user: "22222222-2222-4222-8222-222222222222",
  assistant: "33333333-3333-4333-8333-333333333333",
  citation: "44444444-4444-4444-8444-444444444444",
};

describe("ChatWorkbench", () => {
  afterEach(() => {
    cleanup();
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("creates the guest conversation and renders validated sections as they arrive", async () => {
    const user = userEvent.setup();
    let finish!: () => void;
    const completed = new Promise<void>((resolve) => {
      finish = resolve;
    });
    vi.spyOn(globalThis, "fetch").mockImplementation(
      chatFetch({ conversations: [], stream: answerStream(completed) }),
    );
    const onClose = vi.fn();

    render(
      <ChatWorkbench
        authenticated={false}
        copy={companyPageCopy.en.chat}
        locale="en-US"
        onClose={onClose}
        open
        symbol="AAPL"
      />,
    );

    expect(await screen.findByText("AAPL research")).toBeVisible();
    await user.type(
      screen.getByRole("textbox", { name: companyPageCopy.en.chat.question }),
      "Why did margins rise?",
    );
    await user.click(
      screen.getByRole("button", { name: companyPageCopy.en.chat.send }),
    );

    expect(await screen.findByText(companyPageCopy.en.chat.stages.retrieval)).toBeVisible();
    expect(
      await screen.findByRole("heading", {
        name: companyPageCopy.en.chat.sections.directConclusion,
      }),
    ).toBeVisible();
    expect(screen.getByText("Margins benefited from services mix.")).toBeVisible();
    expect(screen.getByText("1 message remaining")).toBeVisible();
    expect(screen.getByRole("textbox")).toBeDisabled();

    finish();
    expect(await screen.findByRole("link", { name: /Apple 2025 Form 10-K/ })).toHaveAttribute(
      "href",
      "https://www.sec.gov/Archives/aapl-10-k.htm",
    );
    await waitFor(() => expect(screen.getByRole("textbox")).toBeEnabled());

    await user.click(screen.getByRole("button", { name: companyPageCopy.en.chat.close }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("replays a transport failure with the same request UUID", async () => {
    const user = userEvent.setup();
    const requestBodies: string[] = [];
    let sendAttempts = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(
      chatFetch({
        onMessage(body) {
          requestBodies.push(body);
          sendAttempts += 1;
          if (sendAttempts === 1) return new Response(null, { status: 503 });
          return eventResponse(
            frame(1, "accepted", acceptedQuota()) +
              frame(2, "complete", completePayload()),
          );
        },
      }),
    );

    render(
      <ChatWorkbench
        authenticated={false}
        copy={companyPageCopy.en.chat}
        locale="en-US"
        onClose={vi.fn()}
        open
        symbol="AAPL"
      />,
    );
    await screen.findByText("AAPL research");
    await user.type(screen.getByRole("textbox"), "Explain services margins");
    await user.click(screen.getByRole("button", { name: companyPageCopy.en.chat.send }));

    await screen.findByText("Margins benefited from services mix.");
    expect(sendAttempts).toBe(2);
    expect(JSON.parse(requestBodies[0]).client_request_id).toBe(
      JSON.parse(requestBodies[1]).client_request_id,
    );
  });

  it("uses a fresh request UUID when retrying a failed answer", async () => {
    const user = userEvent.setup();
    const bodies: Array<{ path: string; body: string }> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(
      chatFetch({
        onMessage(body, path) {
          bodies.push({ path, body });
          if (path.endsWith("/retry")) {
            return eventResponse(
              frame(1, "accepted", acceptedQuota()) +
                frame(2, "complete", completePayload()),
            );
          }
          return eventResponse(
            frame(1, "accepted", acceptedQuota()) +
              frame(2, "error", {
                code: "CHAT_ANSWER_FAILED",
                retryable: true,
                assistant_message_id: UUIDS.assistant,
                quota: quota(0, 2),
              }),
          );
        },
      }),
    );

    render(
      <ChatWorkbench
        authenticated={false}
        copy={companyPageCopy.en.chat}
        locale="en-US"
        onClose={vi.fn()}
        open
        symbol="AAPL"
      />,
    );
    await screen.findByText("AAPL research");
    await user.type(screen.getByRole("textbox"), "What changed?");
    await user.click(screen.getByRole("button", { name: companyPageCopy.en.chat.send }));
    await user.click(await screen.findByRole("button", { name: companyPageCopy.en.chat.retry }));

    await screen.findByText("Margins benefited from services mix.");
    expect(bodies[1].path).toContain(`/messages/${UUIDS.assistant}/retry`);
    expect(JSON.parse(bodies[0].body).client_request_id).not.toBe(
      JSON.parse(bodies[1].body).client_request_id,
    );
  });

  it("loads cursor-paginated historical messages", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(
      chatFetch({
        messagePages: {
          initial: {
            items: [historicalMessage(UUIDS.user, "Earlier question")],
            next_cursor: "next-page",
          },
          next: {
            items: [
              historicalMessage(
                "55555555-5555-4555-8555-555555555555",
                "Later question",
              ),
            ],
            next_cursor: null,
          },
        },
      }),
    );

    render(
      <ChatWorkbench
        authenticated
        copy={companyPageCopy.en.chat}
        locale="en-US"
        onClose={vi.fn()}
        open
        symbol="AAPL"
      />,
    );

    expect(await screen.findByText("Earlier question")).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: companyPageCopy.en.chat.loadMore }),
    );
    expect(await screen.findByText("Later question")).toBeVisible();
    expect(screen.queryByRole("button", { name: companyPageCopy.en.chat.loadMore })).toBeNull();
  });
});

function chatFetch({
  conversations = [conversation()],
  stream,
  onMessage,
  messagePages,
}: {
  conversations?: ReturnType<typeof conversation>[];
  stream?: Response;
  onMessage?: (body: string, path: string) => Response;
  messagePages?: {
    initial: { items: ReturnType<typeof historicalMessage>[]; next_cursor: string | null };
    next: { items: ReturnType<typeof historicalMessage>[]; next_cursor: string | null };
  };
} = {}) {
  return async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    const method = init?.method ?? "GET";
    if (path.includes("chat-readiness")) return Response.json(readiness());
    if (path.endsWith("/chat-quota")) return Response.json(quota(0, 2));
    if (path.endsWith("/conversations") && method === "GET") {
      return Response.json(conversations);
    }
    if (path.endsWith("/conversations") && method === "POST") {
      return Response.json(conversation(), { status: 201 });
    }
    if (path.includes("/messages") && method === "GET") {
      if (messagePages) {
        return Response.json(path.includes("cursor=") ? messagePages.next : messagePages.initial);
      }
      return Response.json({ items: [], next_cursor: null });
    }
    if (path.includes("/messages") && method === "POST") {
      const body = String(init?.body ?? "");
      return onMessage?.(body, path) ?? stream ?? eventResponse("");
    }
    throw new Error(`Unexpected request: ${method} ${path}`);
  };
}

function historicalMessage(id: string, content: string) {
  return {
    id,
    conversation_id: UUIDS.conversation,
    reply_to_message_id: null,
    role: "user" as const,
    state: "completed" as const,
    content,
    locale: "en-US" as const,
    evidence_coverage: null,
    error_code: null,
    attempt_count: 0,
    created_at: id === UUIDS.user
      ? "2026-07-15T00:00:00Z"
      : "2026-07-15T00:01:00Z",
    completed_at: "2026-07-15T00:01:00Z",
    citations: [],
  };
}

function answerStream(completed: Promise<void>) {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(
          encoder.encode(
            frame(1, "accepted", acceptedQuota()) +
              frame(2, "stage", {
                stage: "retrieval",
                status_key: "chat.stage.retrieval",
              }) +
              frame(3, "section", {
                section: "direct_conclusion",
                delta: "Margins benefited from services mix.",
              }),
          ),
        );
        void completed.then(() => {
          controller.enqueue(
            encoder.encode(
              frame(4, "citation", citation()) +
                frame(5, "complete", completePayload()),
            ),
          );
          controller.close();
        });
      },
    }),
    { headers: { "content-type": "text/event-stream" } },
  );
}

function eventResponse(body: string) {
  return new Response(body, { headers: { "content-type": "text/event-stream" } });
}

function frame(id: number, event: string, payload: unknown) {
  return `id: ${id}\nevent: ${event}\ndata: ${JSON.stringify(payload)}\n\n`;
}

function conversation() {
  return {
    id: UUIDS.conversation,
    company_id: 1,
    title: "AAPL research",
    locale: "en-US",
    expires_at: "2026-07-22T00:00:00Z",
    archived_at: null,
    created_at: "2026-07-15T00:00:00Z",
    updated_at: "2026-07-15T00:00:00Z",
  };
}

function quota(used: number, remaining: number) {
  return {
    limit: 2,
    used,
    remaining,
    resets_at: "2026-07-16T00:00:00Z",
  };
}

function acceptedQuota() {
  return {
    user_message_id: UUIDS.user,
    assistant_message_id: UUIDS.assistant,
    conversation_id: UUIDS.conversation,
    quota: quota(1, 1),
  };
}

function citation() {
  return {
    id: UUIDS.citation,
    ordinal: 0,
    source_kind: "filing",
    source_id: "10-k:item-7",
    title: "Apple 2025 Form 10-K",
    source_url: "https://www.sec.gov/Archives/aapl-10-k.htm",
    source_anchor: "Item 7",
    excerpt: "Services mix increased gross margin.",
    published_at: "2025-10-31T00:00:00Z",
    retrieved_at: "2026-07-15T00:00:00Z",
    source_tier: "primary",
    verification: "verified",
  };
}

function completePayload() {
  return {
    message: {
      id: UUIDS.assistant,
      conversation_id: UUIDS.conversation,
      reply_to_message_id: UUIDS.user,
      role: "assistant",
      state: "completed",
      content:
        "## Conclusion\n\nMargins benefited from services mix.\n\n## Key evidence\n\n- Services grew.\n\n## Risks and uncertainties\n\n- Mix can reverse.\n\n## Sources\n\n- [1] Apple 2025 Form 10-K",
      locale: "en-US",
      evidence_coverage: "complete",
      error_code: null,
      attempt_count: 0,
      created_at: "2026-07-15T00:00:00Z",
      completed_at: "2026-07-15T00:00:02Z",
      citations: [citation()],
    },
    citations: [citation()],
    evidence_coverage: "complete",
    quota: quota(1, 1),
  };
}

function readiness() {
  const ready = { state: "ready", action: null };
  return {
    company_symbol: "AAPL",
    intelligence: ready,
    filing_text: ready,
    filing_index: ready,
    supply_chain_graph: ready,
    web_recency: ready,
  };
}
