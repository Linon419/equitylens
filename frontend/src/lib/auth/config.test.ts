import { afterEach, describe, expect, it } from "vitest";

import { authConfig } from "./config";

describe("authConfig", () => {
  const original = process.env;

  afterEach(() => {
    process.env = original;
  });

  it("uses server-only backend URL and parses cookie security", () => {
    process.env = {
      ...original,
      BACKEND_URL: "http://api:8000/",
      COOKIE_SECURE: "false",
    };

    expect(authConfig()).toEqual({
      backendUrl: "http://api:8000",
      cookieSecure: false,
    });
  });

  it("requires the backend URL", () => {
    process.env = { ...original };
    delete process.env.BACKEND_URL;

    expect(() => authConfig()).toThrow("BACKEND_URL is required");
  });
});
