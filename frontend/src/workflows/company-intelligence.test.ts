import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { companyIntelligenceWorkflow } from "./company-intelligence";

describe("companyIntelligenceWorkflow", () => {
  beforeEach(() => {
    vi.stubEnv("BACKEND_URL", "https://api.example.com");
    vi.stubEnv("INTERNAL_JOB_SECRET", "internal-secret");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("invokes FastAPI steps in durable order", async () => {
    const requests: Request[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
        requests.push(new Request(input, init));
        return new Response(null, { status: 204 });
      }),
    );

    await companyIntelligenceWorkflow("job-123");

    expect(requests.map((request) => new URL(request.url).pathname)).toEqual([
      "/api/v1/internal/jobs/job-123/download",
      "/api/v1/internal/jobs/job-123/parse",
      "/api/v1/internal/jobs/job-123/analyze",
      "/api/v1/internal/jobs/job-123/verify",
      "/api/v1/internal/jobs/job-123/localize",
    ]);
    expect(requests[0].headers.get("authorization")).toBe(
      "Bearer internal-secret",
    );
    expect(requests[0].headers.get("x-idempotency-key")).toBe(
      "job-123:download:v1",
    );
  });

  it("raises a bounded error when a backend step fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(null, { status: 503 })),
    );

    await expect(companyIntelligenceWorkflow("job-123")).rejects.toThrow(
      "Backend step download failed: 503",
    );
  });
});
