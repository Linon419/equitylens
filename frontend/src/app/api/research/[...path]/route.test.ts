import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

const backendRequest = vi.hoisted(() => vi.fn());

vi.mock("@/lib/research/backend", () => ({
  researchBackendRequest: backendRequest,
}));

import {
  DELETE,
  GET,
  PATCH,
  POST,
  isAllowedResearchRequest,
} from "./route";

describe("research BFF route", () => {
  afterEach(() => {
    backendRequest.mockReset();
    vi.restoreAllMocks();
  });

  it.each([
    ["GET", "companies/search"],
    ["GET", "companies/AAPL"],
    ["GET", "companies/AAPL/market"],
    ["GET", "companies/AAPL/financials"],
    ["GET", "companies/AAPL/intelligence"],
    ["GET", "companies/AAPL/supply-chain-graph"],
    ["GET", "jobs/11111111-1111-4111-8111-111111111111"],
    ["GET", "agent-quota"],
    ["GET", "watchlist"],
    ["GET", "companies/AAPL/chat-readiness"],
    ["GET", "companies/AAPL/conversations"],
    ["GET", "conversations/11111111-1111-4111-8111-111111111111"],
    ["GET", "conversations/11111111-1111-4111-8111-111111111111/messages"],
    ["GET", "chat-quota"],
    ["POST", "companies/AAPL/sync"],
    ["POST", "companies/AAPL/supply-chain-graph/sync"],
    ["POST", "jobs/11111111-1111-4111-8111-111111111111/retry"],
    ["POST", "watchlist/AAPL"],
    ["POST", "companies/AAPL/chat-index/sync"],
    ["POST", "companies/AAPL/conversations"],
    ["POST", "conversations/11111111-1111-4111-8111-111111111111/messages"],
    [
      "POST",
      "conversations/11111111-1111-4111-8111-111111111111/messages/22222222-2222-4222-8222-222222222222/retry",
    ],
    ["PATCH", "conversations/11111111-1111-4111-8111-111111111111"],
    ["DELETE", "watchlist/AAPL"],
    ["DELETE", "conversations/11111111-1111-4111-8111-111111111111"],
  ])("allows %s %s", (method, path) => {
    expect(isAllowedResearchRequest(method, path)).toBe(true);
  });

  it.each([
    ["POST", "companies/search"],
    ["GET", "internal/jobs/abc/download"],
    ["DELETE", "companies/AAPL"],
    ["GET", "../auth/me"],
    ["GET", "%2e%2e/auth/me"],
    ["DELETE", "companies/AAPL/supply-chain-graph"],
  ])("blocks %s %s", (method, path) => {
    expect(isAllowedResearchRequest(method, path)).toBe(false);
  });

  it("rejects a mutation with an invalid origin", async () => {
    const response = await POST(
      new NextRequest("https://example.com/api/research/companies/AAPL/sync", {
        method: "POST",
        headers: { "sec-fetch-site": "same-origin" },
      }),
      context("companies", "AAPL", "sync"),
    );

    expect(response.status).toBe(403);
    expect(backendRequest).not.toHaveBeenCalled();
  });

  it("rejects a mutation with a cross-site fetch context", async () => {
    const response = await DELETE(
      new NextRequest("https://example.com/api/research/watchlist/AAPL", {
        method: "DELETE",
        headers: {
          origin: "https://example.com",
          "sec-fetch-site": "cross-site",
        },
      }),
      context("watchlist", "AAPL"),
    );

    expect(response.status).toBe(403);
    expect(backendRequest).not.toHaveBeenCalled();
  });

  it("preserves JSON, status, Retry-After, and a guest cookie", async () => {
    backendRequest.mockResolvedValue({
      response: Response.json(
        { code: "AGENT_DAILY_QUOTA_EXCEEDED" },
        { status: 429, headers: { "retry-after": "3600" } },
      ),
      guestCookie: "equitylens_guest=signed; HttpOnly; Path=/",
    });

    const response = await GET(
      new NextRequest("https://example.com/api/research/agent-quota"),
      context("agent-quota"),
    );

    expect(response.status).toBe(429);
    expect(response.headers.get("retry-after")).toBe("3600");
    expect(response.headers.get("set-cookie")).toContain("equitylens_guest=");
    await expect(response.json()).resolves.toEqual({
      code: "AGENT_DAILY_QUOTA_EXCEEDED",
    });
  });

  it("rejects request bodies larger than 64 KiB", async () => {
    const response = await POST(
      new NextRequest("https://example.com/api/research/companies/AAPL/sync", {
        method: "POST",
        headers: {
          origin: "https://example.com",
          "sec-fetch-site": "same-origin",
          "content-length": "65537",
        },
        body: "x".repeat(65_537),
      }),
      context("companies", "AAPL", "sync"),
    );

    expect(response.status).toBe(413);
    expect(backendRequest).not.toHaveBeenCalled();
  });

  it.each([404, 422, 429])("forwards an upstream %s response", async (status) => {
    backendRequest.mockResolvedValue({
      response: Response.json({ code: `CHAT_${status}` }, { status }),
    });
    const response = await GET(
      new NextRequest("https://example.com/api/research/chat-quota"),
      context("chat-quota"),
    );

    expect(response.status).toBe(status);
    await expect(response.json()).resolves.toEqual({ code: `CHAT_${status}` });
  });

  it("forwards SSE incrementally with streaming headers", async () => {
    let releaseSecond!: () => void;
    let secondChunkReleased = false;
    const second = new Promise<void>((resolve) => {
      releaseSecond = resolve;
    });
    const upstream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode("event: accepted\n\n"));
        void second.then(() => {
          secondChunkReleased = true;
          controller.enqueue(new TextEncoder().encode("event: complete\n\n"));
          controller.close();
        });
      },
    });
    backendRequest.mockResolvedValue({
      response: new Response(upstream, {
        headers: {
          "content-type": "text/event-stream; charset=utf-8",
          "cache-control": "no-cache, no-transform",
          "x-accel-buffering": "no",
        },
      }),
    });
    const response = await POST(
      mutationRequest("conversations/11111111-1111-4111-8111-111111111111/messages"),
      context(
        "conversations",
        "11111111-1111-4111-8111-111111111111",
        "messages",
      ),
    );
    const reader = response.body!.getReader();

    const first = await reader.read();
    expect(new TextDecoder().decode(first.value)).toContain("event: accepted");
    expect(secondChunkReleased).toBe(false);
    expect(response.headers.get("cache-control")).toBe("no-cache, no-transform");
    expect(response.headers.get("x-accel-buffering")).toBe("no");

    releaseSecond();
    const next = await reader.read();
    expect(new TextDecoder().decode(next.value)).toContain("event: complete");
  });

  it("accepts PATCH only for conversation rename", async () => {
    backendRequest.mockResolvedValue({ response: Response.json({ title: "Renamed" }) });
    const id = "11111111-1111-4111-8111-111111111111";

    const response = await PATCH(
      mutationRequest(`conversations/${id}`, "PATCH"),
      context("conversations", id),
    );

    expect(response.status).toBe(200);
    expect(isAllowedResearchRequest("PATCH", `conversations/${id}/messages`)).toBe(
      false,
    );
  });
});

function context(...path: string[]) {
  return { params: Promise.resolve({ path }) };
}

function mutationRequest(path: string, method = "POST") {
  return new NextRequest(`https://example.com/api/research/${path}`, {
    method,
    headers: {
      origin: "https://example.com",
      "sec-fetch-site": "same-origin",
      "content-type": "application/json",
    },
    body: "{}",
  });
}
