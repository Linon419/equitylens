import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

const backendRequest = vi.hoisted(() => vi.fn());

vi.mock("@/lib/research/backend", () => ({
  researchBackendRequest: backendRequest,
}));

import {
  DELETE,
  GET,
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
    ["POST", "companies/AAPL/sync"],
    ["POST", "companies/AAPL/supply-chain-graph/sync"],
    ["POST", "jobs/11111111-1111-4111-8111-111111111111/retry"],
    ["POST", "watchlist/AAPL"],
    ["DELETE", "watchlist/AAPL"],
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
});

function context(...path: string[]) {
  return { params: Promise.resolve({ path }) };
}
