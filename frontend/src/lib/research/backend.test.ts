import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { accessCookieName, refreshCookieName } from "@/lib/auth/cookies";
import { GUEST_COOKIE } from "./guest";
import { researchBackendRequest } from "./backend";

const tokens = {
  access_token: "new-access",
  refresh_token: "new-refresh",
  token_type: "bearer",
  access_expires_in: 900,
  refresh_expires_in: 2_592_000,
};

describe("research backend requests", () => {
  afterEach(() => vi.restoreAllMocks());

  it("sends a bearer token for an authenticated request", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(Response.json({ symbol: "AAPL" }));
    const request = requestWithCookies(`${accessCookieName}=access-token`);

    await researchBackendRequest(request, "companies/AAPL");

    expect(fetchMock).toHaveBeenCalledOnce();
    expect(requestHeader(fetchMock, 0, "authorization")).toBe(
      "Bearer access-token",
    );
  });

  it("sends a signed assertion and returns a pending guest cookie", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(Response.json({ remaining: 2 }));
    const request = new NextRequest("https://example.com/api/research/agent-quota", {
      headers: { "x-forwarded-for": "203.0.113.10" },
    });

    const result = await researchBackendRequest(request, "agent-quota");

    expect(requestHeader(fetchMock, 0, "x-guest-assertion")).toContain(".");
    expect(result.guestCookie).toContain(`${GUEST_COOKIE}=`);
  });

  it("refreshes once and replays an authenticated request once", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(Response.json({ code: "AUTH_REQUIRED" }, { status: 401 }))
      .mockResolvedValueOnce(Response.json(tokens))
      .mockResolvedValueOnce(Response.json({ symbol: "AAPL" }));
    const request = requestWithCookies(
      `${accessCookieName}=old-access; ${refreshCookieName}=refresh-token`,
    );

    const result = await researchBackendRequest(request, "companies/AAPL");

    expect(result.response.status).toBe(200);
    expect(result.rotatedTokens?.access_token).toBe("new-access");
    expect(requestHeader(fetchMock, 2, "authorization")).toBe(
      "Bearer new-access",
    );
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("returns a second 401 without another refresh loop", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(Response.json({ code: "AUTH_REQUIRED" }, { status: 401 }))
      .mockResolvedValueOnce(Response.json(tokens))
      .mockResolvedValueOnce(Response.json({ code: "AUTH_REQUIRED" }, { status: 401 }));
    const request = requestWithCookies(
      `${accessCookieName}=old-access; ${refreshCookieName}=refresh-token`,
    );

    const result = await researchBackendRequest(request, "companies/AAPL");

    expect(result.response.status).toBe(401);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("forwards only approved request headers and preserves the upstream response", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json(
        { code: "AGENT_DAILY_QUOTA_EXCEEDED" },
        { status: 429, headers: { "retry-after": "3600" } },
      ),
    );
    const request = new NextRequest("https://example.com/api/research/agent-quota", {
      headers: {
        "accept-language": "zh-CN",
        "x-forwarded-for": "203.0.113.10",
        "x-untrusted-header": "blocked",
      },
    });

    const result = await researchBackendRequest(request, "agent-quota");

    expect(result.response.status).toBe(429);
    expect(result.response.headers.get("retry-after")).toBe("3600");
    expect(requestHeader(fetchMock, 0, "accept-language")).toBe("zh-CN");
    expect(requestHeader(fetchMock, 0, "x-untrusted-header")).toBeNull();
  });

  it("propagates the caller abort signal to every backend attempt", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(Response.json({ symbol: "AAPL" }));
    const controller = new AbortController();
    const request = new NextRequest("https://example.com/api/research/companies/AAPL", {
      signal: controller.signal,
    });

    await researchBackendRequest(request, "companies/AAPL");

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.signal).toBe(request.signal);
  });
});

function requestWithCookies(cookie: string) {
  return new NextRequest("https://example.com/api/research/companies/AAPL", {
    headers: { cookie },
  });
}

function requestHeader(
  fetchMock: ReturnType<typeof vi.spyOn>,
  index: number,
  name: string,
) {
  const init = fetchMock.mock.calls[index]?.[1] as RequestInit;
  return new Headers(init.headers).get(name);
}
