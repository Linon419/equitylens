import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { accessCookieName, refreshCookieName } from "@/lib/auth/cookies";
import { POST as logout } from "./logout/route";
import { GET as me } from "./me/route";
import { PATCH as preferences } from "./preferences/route";
import { POST as refresh } from "./refresh/route";

const tokens = {
  access_token: "new-access",
  refresh_token: "new-refresh",
  token_type: "bearer",
  access_expires_in: 900,
  refresh_expires_in: 2_592_000,
};

describe("session Route Handlers", () => {
  afterEach(() => vi.restoreAllMocks());

  it("returns the current user", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json({ id: 1, email: "investor@example.com" }),
    );
    const request = new NextRequest("https://example.com/api/auth/me", {
      headers: { cookie: `${accessCookieName}=access` },
    });

    const response = await me(request);

    expect(response.status).toBe(200);
    expect((await response.json()).email).toBe("investor@example.com");
  });

  it("rotates refresh cookies", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json(tokens));
    const request = new NextRequest("https://example.com/api/auth/refresh", {
      method: "POST",
      headers: {
        origin: "https://example.com",
        cookie: `${refreshCookieName}=old-refresh`,
      },
    });

    const response = await refresh(request);

    expect(response.cookies.get(accessCookieName)?.value).toBe("new-access");
    expect(response.cookies.get(refreshCookieName)?.value).toBe("new-refresh");
  });

  it("preserves cookies for a concurrent stale refresh", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json({ code: "AUTH_REFRESH_STALE" }, { status: 409 }),
    );
    const request = new NextRequest("https://example.com/api/auth/refresh", {
      method: "POST",
      headers: {
        origin: "https://example.com",
        cookie: `${refreshCookieName}=old-refresh`,
      },
    });

    const response = await refresh(request);

    expect(response.status).toBe(409);
    expect(response.cookies.get(refreshCookieName)).toBeUndefined();
  });

  it("clears cookies after logout", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, { status: 204 }),
    );
    const request = new NextRequest("https://example.com/api/auth/logout", {
      method: "POST",
      headers: {
        origin: "https://example.com",
        cookie: `${refreshCookieName}=refresh`,
      },
    });

    const response = await logout(request);

    expect(response.status).toBe(204);
    expect(response.cookies.get(refreshCookieName)?.maxAge).toBe(0);
  });

  it("persists locale preferences", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json({
        id: 1,
        email: "investor@example.com",
        preferred_locale: "zh-CN",
      }),
    );
    const request = new NextRequest(
      "https://example.com/api/auth/preferences",
      {
        method: "PATCH",
        headers: {
          origin: "https://example.com",
          cookie: `${accessCookieName}=access`,
          "content-type": "application/json",
        },
        body: JSON.stringify({ preferred_locale: "zh-CN" }),
      },
    );

    const response = await preferences(request);

    expect(response.status).toBe(200);
    expect((await response.json()).preferred_locale).toBe("zh-CN");
  });
});
