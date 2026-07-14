import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { supplyChainGraphWorkflow } from "./supply-chain-graph";

describe("supplyChainGraphWorkflow", () => {
  beforeEach(() => {
    vi.stubEnv("BACKEND_URL", "https://api.example.com/");
    vi.stubEnv("INTERNAL_JOB_SECRET", "internal-secret");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("invokes graph stages in durable order", async () => {
    const requests: Request[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
        requests.push(new Request(input, init));
        return new Response(null, { status: 204 });
      }),
    );

    await supplyChainGraphWorkflow("graph-job-123");

    expect(requests.map((request) => new URL(request.url).pathname)).toEqual([
      "/api/v1/internal/jobs/graph-job-123/supply-chain-graph/collect",
      "/api/v1/internal/jobs/graph-job-123/supply-chain-graph/extract",
      "/api/v1/internal/jobs/graph-job-123/supply-chain-graph/resolve",
      "/api/v1/internal/jobs/graph-job-123/supply-chain-graph/verify",
      "/api/v1/internal/jobs/graph-job-123/supply-chain-graph/localize",
      "/api/v1/internal/jobs/graph-job-123/supply-chain-graph/publish",
    ]);
    expect(requests[0].headers.get("authorization")).toBe(
      "Bearer internal-secret",
    );
    expect(requests[0].headers.get("x-idempotency-key")).toBe(
      "graph-job-123:supply-chain-graph:collect:v1",
    );
  });

  it("raises a bounded error when a graph stage fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(null, { status: 503 })),
    );

    await expect(supplyChainGraphWorkflow("graph-job-123")).rejects.toThrow(
      "Backend graph step collect failed: 503",
    );
  });
});
