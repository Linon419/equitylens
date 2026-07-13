import { describe, expect, it } from "vitest";

import { csrfCookieName } from "@/lib/auth/cookies";
import { GET } from "./route";

describe("GET /api/auth/csrf", () => {
  it("returns a token and sets an HttpOnly strict cookie", async () => {
    const response = await GET();
    const body = await response.json();

    expect(body.token).toHaveLength(43);
    expect(response.cookies.get(csrfCookieName)?.value).toBe(body.token);
    expect(response.cookies.get(csrfCookieName)?.httpOnly).toBe(true);
    expect(response.cookies.get(csrfCookieName)?.sameSite).toBe("strict");
  });
});
