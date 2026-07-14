import { describe, expect, it } from "vitest";

import { supplyChainGraphFixture } from "@/features/company/test-fixtures";

import { parseResearchResponse } from "./types";

describe("supply-chain graph response parser", () => {
  it("parses the graph contract", () => {
    const graph = parseResearchResponse(
      "supplyChainGraph",
      supplyChainGraphFixture,
    );

    expect(graph.snapshot.symbol).toBe("AAPL");
    expect(graph.nodes).toHaveLength(25);
    expect(graph.edges[0].citations[0].excerpt).toContain("fixture evidence");
  });

  it("rejects a graph without nodes", () => {
    expect(() =>
      parseResearchResponse("supplyChainGraph", {
        ...supplyChainGraphFixture,
        nodes: undefined,
      }),
    ).toThrow("missing nodes");
  });

  it("parses graph synchronization responses", () => {
    const response = parseResearchResponse("graphSync", {
      status: "accepted",
      job: supplyChainGraphFixture.refresh_job,
      job_id: supplyChainGraphFixture.refresh_job?.id,
      snapshot_id: null,
      quota: supplyChainGraphFixture.quota,
    });

    expect(response.status).toBe("accepted");
    expect(response.quota.limit).toBe(2);
  });
});
