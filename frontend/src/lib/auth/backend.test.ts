import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authenticatedBackendRequest } from "./backend";

describe("authenticated backend requests", () => {
  afterEach(() => vi.restoreAllMocks());

  it("refreshes once after an expired access token", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        Response.json({ code: "AUTH_REQUIRED" }, { status: 401 }),
      )
      .mockResolvedValueOnce(
        Response.json({
          access_token: "new-access",
          refresh_token: "new-refresh",
          token_type: "bearer",
          access_expires_in: 900,
          refresh_expires_in: 2_592_000,
        }),
      )
      .mockResolvedValueOnce(
        Response.json({ id: 1, email: "a@example.com" }),
      );
    const request = new NextRequest("https://example.com/api/auth/me", {
      headers: {
        cookie:
          "equitylens_access=old-access; equitylens_refresh=old-refresh",
      },
    });

    const result = await authenticatedBackendRequest(request, "/auth/me");

    expect(result.response.status).toBe(200);
    expect(result.rotatedTokens?.access_token).toBe("new-access");
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("returns auth required when the access cookie is absent", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    const request = new NextRequest("https://example.com/api/auth/me");

    const result = await authenticatedBackendRequest(request, "/auth/me");

    expect(result.response.status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
