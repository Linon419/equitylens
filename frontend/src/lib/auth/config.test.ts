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

  it("uses the deployment URL when a private backend binding is absent", () => {
    process.env = {
      ...original,
      BACKEND_URL: "",
      VERCEL_ENV: "preview",
      VERCEL_URL: "equitylens-preview.vercel.app",
      VERCEL_PROJECT_PRODUCTION_URL: "equitylens.vercel.app",
    };

    expect(authConfig().backendUrl).toBe(
      "https://equitylens-preview.vercel.app",
    );
  });

  it("uses the public project URL in production", () => {
    process.env = {
      ...original,
      BACKEND_URL: "",
      VERCEL_ENV: "production",
      VERCEL_URL: "equitylens-deployment.vercel.app",
      VERCEL_PROJECT_PRODUCTION_URL: "equitylens.vercel.app",
    };

    expect(authConfig().backendUrl).toBe("https://equitylens.vercel.app");
  });

  it("requires one backend origin", () => {
    process.env = { ...original };
    delete process.env.BACKEND_URL;
    delete process.env.VERCEL_URL;
    delete process.env.VERCEL_PROJECT_PRODUCTION_URL;
    delete process.env.VERCEL_ENV;

    expect(() => authConfig()).toThrow(
      "BACKEND_URL, VERCEL_URL, or VERCEL_PROJECT_PRODUCTION_URL is required",
    );
  });
});
