import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { proxy } from "./proxy";

describe("locale proxy", () => {
  it("redirects a Chinese browser to the Chinese route", () => {
    const request = new NextRequest("https://example.com/", {
      headers: { "accept-language": "zh-CN,zh;q=0.9,en;q=0.8" },
    });

    const response = proxy(request);

    expect(response?.status).toBe(307);
    expect(response?.headers.get("location")).toBe("https://example.com/zh-CN");
  });

  it("keeps a localized route in place", () => {
    const request = new NextRequest("https://example.com/en-US/company/AAPL");

    const response = proxy(request);

    expect(response?.headers.get("location")).toBeNull();
  });
});
