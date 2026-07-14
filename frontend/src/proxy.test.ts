import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { GUEST_COOKIE, signGuestCookie } from "@/lib/research/guest";
import { proxy } from "./proxy";

describe("locale proxy", () => {
  it("redirects a Chinese browser to the Chinese route", async () => {
    const request = new NextRequest("https://example.com/", {
      headers: { "accept-language": "zh-CN,zh;q=0.9,en;q=0.8" },
    });

    const response = await proxy(request);

    expect(response?.status).toBe(307);
    expect(response?.headers.get("location")).toBe("https://example.com/zh-CN");
  });

  it("keeps a localized route in place", async () => {
    const request = new NextRequest("https://example.com/en-US/company/AAPL");

    const response = await proxy(request);

    expect(response?.headers.get("location")).toBeNull();
  });

  it("establishes one signed guest identity on the initial page response", async () => {
    const response = await proxy(
      new NextRequest("https://example.com/en-US/companies/AAPL"),
    );

    expect(response.headers.get("set-cookie")).toContain(`${GUEST_COOKIE}=`);
  });

  it("preserves an existing signed guest identity", async () => {
    const secret = process.env.GUEST_SIGNING_SECRET!;
    const guestId = "11111111-1111-4111-8111-111111111111";
    const signed = await signGuestCookie(guestId, secret);
    const response = await proxy(
      new NextRequest("https://example.com/en-US/companies/AAPL", {
        headers: { cookie: `${GUEST_COOKIE}=${signed}` },
      }),
    );

    expect(response.headers.get("set-cookie")).toBeNull();
  });
});
