import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { accessCookieName, csrfCookieName } from "@/lib/auth/cookies";
import { POST } from "./route";

describe("POST /api/auth/google/callback", () => {
  afterEach(() => vi.restoreAllMocks());

  it("exchanges a valid credential and sets session cookies", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json({
        access_token: "access",
        refresh_token: "refresh",
        token_type: "bearer",
        access_expires_in: 900,
        refresh_expires_in: 2_592_000,
        user: {
          id: 1,
          email: "a@example.com",
          preferred_locale: "en-US",
        },
      }),
    );
    const request = new NextRequest(
      "https://example.com/api/auth/google/callback",
      {
        method: "POST",
        headers: {
          origin: "https://example.com",
          cookie: `${csrfCookieName}=csrf-token`,
          "content-type": "application/json",
        },
        body: JSON.stringify({
          credential: "google-token",
          csrf_token: "csrf-token",
          preferred_locale: "en-US",
        }),
      },
    );

    const response = await POST(request);

    expect(response.status).toBe(200);
    expect(response.cookies.get(accessCookieName)?.value).toBe("access");
    expect(response.cookies.get(csrfCookieName)?.maxAge).toBe(0);
  });

  it("rejects a cross-origin callback before contacting the backend", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    const request = new NextRequest(
      "https://example.com/api/auth/google/callback",
      {
        method: "POST",
        headers: {
          origin: "https://evil.example",
          cookie: `${csrfCookieName}=csrf-token`,
          "content-type": "application/json",
        },
        body: JSON.stringify({
          credential: "google-token",
          csrf_token: "csrf-token",
          preferred_locale: "en-US",
        }),
      },
    );

    const response = await POST(request);

    expect(response.status).toBe(400);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
