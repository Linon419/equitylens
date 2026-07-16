import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { isSameOrigin, isValidCsrf, safeReturnPath } from "./security";

describe("auth security", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("allows internal return paths and rejects external paths", () => {
    expect(safeReturnPath("/zh-CN/dashboard", "/en-US/dashboard")).toBe(
      "/zh-CN/dashboard",
    );
    expect(safeReturnPath("//evil.example", "/en-US/dashboard")).toBe(
      "/en-US/dashboard",
    );
    expect(
      safeReturnPath("https://evil.example", "/en-US/dashboard"),
    ).toBe("/en-US/dashboard");
    expect(safeReturnPath("/\\evil.example", "/en-US/dashboard")).toBe(
      "/en-US/dashboard",
    );
  });

  it("requires matching request and application origins", () => {
    vi.stubEnv("FRONTEND_URL", "https://equitylens.example");
    const request = new NextRequest(
      "http://internal-next-host:3000/api/auth/logout",
      { headers: { origin: "https://equitylens.example" } },
    );
    const crossOrigin = new NextRequest(
      "http://internal-next-host:3000/api/auth/logout",
      { headers: { origin: "https://evil.example" } },
    );

    expect(isSameOrigin(request)).toBe(true);
    expect(isSameOrigin(crossOrigin)).toBe(false);
  });

  it("uses the forwarded deployment origin when FRONTEND_URL is absent", () => {
    vi.stubEnv("FRONTEND_URL", "");
    const request = new NextRequest(
      "http://internal-next-host:3000/api/auth/logout",
      {
        headers: {
          origin: "https://equitylens-preview.vercel.app",
          "x-forwarded-host": "equitylens-preview.vercel.app",
          "x-forwarded-proto": "https",
        },
      },
    );

    expect(isSameOrigin(request)).toBe(true);
  });

  it("compares complete CSRF values", () => {
    expect(isValidCsrf("token-value", "token-value")).toBe(true);
    expect(isValidCsrf("token-value", "different")).toBe(false);
    expect(isValidCsrf(null, "token-value")).toBe(false);
  });
});
