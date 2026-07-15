import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { filingIndexWorkflow } from "./filing-index";

describe("filingIndexWorkflow", () => {
  beforeEach(() => {
    vi.stubEnv("BACKEND_URL", "https://api.example.com/");
    vi.stubEnv("INTERNAL_JOB_SECRET", "internal-secret");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("invokes the idempotent FastAPI filing-index step", async () => {
    const requests: Request[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
        requests.push(new Request(input, init));
        return new Response(null, { status: 204 });
      }),
    );

    await filingIndexWorkflow("index-job-123");

    expect(new URL(requests[0].url).pathname).toBe(
      "/api/v1/internal/jobs/index-job-123/filing-index",
    );
    expect(requests[0].headers.get("authorization")).toBe(
      "Bearer internal-secret",
    );
    expect(requests[0].headers.get("x-idempotency-key")).toBe(
      "index-job-123:filing-index:v1",
    );
  });

  it("raises a bounded error when indexing fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(null, { status: 503 })),
    );

    await expect(filingIndexWorkflow("index-job-123")).rejects.toThrow(
      "Backend filing-index step failed: 503",
    );
  });
});
