import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { start } from "workflow/api";

import { POST } from "./route";

vi.mock("workflow/api", () => ({ start: vi.fn() }));

const mockedStart = vi.mocked(start);

function request(secret: string, idempotencyKey = "index-job-123") {
  return new Request("http://localhost/api/internal/workflows/filing-index", {
    method: "POST",
    headers: {
      authorization: `Bearer ${secret}`,
      "content-type": "application/json",
      "x-idempotency-key": idempotencyKey,
    },
    body: JSON.stringify({ job_id: "index-job-123" }),
  });
}

describe("POST filing-index workflow trigger", () => {
  beforeEach(() => {
    vi.stubEnv("INTERNAL_JOB_SECRET", "internal-secret");
    mockedStart.mockResolvedValue({ runId: "index-run-123" } as never);
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllEnvs();
  });

  it("starts one filing-index workflow", async () => {
    const response = await POST(request("internal-secret"));

    expect(response.status).toBe(202);
    await expect(response.json()).resolves.toEqual({ run_id: "index-run-123" });
    expect(mockedStart.mock.calls[0][1]).toEqual(["index-job-123"]);
  });

  it("rejects an invalid internal secret", async () => {
    const response = await POST(request("wrong-secret"));

    expect(response.status).toBe(401);
    expect(mockedStart).not.toHaveBeenCalled();
  });

  it("rejects a mismatched idempotency key", async () => {
    const response = await POST(request("internal-secret", "other-job"));

    expect(response.status).toBe(400);
    expect(mockedStart).not.toHaveBeenCalled();
  });
});
