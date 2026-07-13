import { NextResponse } from "next/server";
import { describe, expect, it } from "vitest";

import {
  accessCookieName,
  refreshCookieName,
  setSessionCookies,
} from "./cookies";

describe("session cookies", () => {
  it("sets HttpOnly same-site token cookies", () => {
    const response = NextResponse.json({ ok: true });
    setSessionCookies(response, {
      access_token: "access",
      refresh_token: "refresh",
      token_type: "bearer",
      access_expires_in: 900,
      refresh_expires_in: 2_592_000,
    });

    expect(response.cookies.get(accessCookieName)?.httpOnly).toBe(true);
    expect(response.cookies.get(accessCookieName)?.sameSite).toBe("lax");
    expect(response.cookies.get(refreshCookieName)?.httpOnly).toBe(true);
  });
});
