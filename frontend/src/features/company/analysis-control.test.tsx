import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/components/session-provider", () => ({
  useSession: () => ({ user: null, loading: false }),
}));

import { AnalysisControl, analysisCopy } from "./analysis-control";
import {
  intelligenceFixture,
  jobFixture,
  quotaFixture,
} from "./test-fixtures";

describe("AnalysisControl", () => {
  beforeEach(() => vi.useFakeTimers());

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("polls every pipeline state and refreshes intelligence on completion", async () => {
    const completed = vi.fn();
    const states = [
      "downloading",
      "parsing",
      "analyzing",
      "verifying",
      "localizing",
      "completed",
    ];
    const fetchMock = vi.spyOn(globalThis, "fetch");
    fetchMock.mockResolvedValueOnce(
      Response.json(
        {
          status: "accepted",
          job: jobFixture,
          snapshot_id: null,
          quota: { ...quotaFixture, used: 1, remaining: 1 },
        },
        { status: 202 },
      ),
    );
    for (const state of states) {
      fetchMock.mockResolvedValueOnce(
        Response.json({
          ...jobFixture,
          state,
          current_step: state,
          snapshot_id:
            state === "completed" ? intelligenceFixture.snapshot_id : null,
        }),
      );
    }
    fetchMock
      .mockResolvedValueOnce(Response.json(intelligenceFixture))
      .mockResolvedValueOnce(
        Response.json({ ...quotaFixture, used: 1, remaining: 1 }),
      );

    render(
      <AnalysisControl
        copy={analysisCopy.en}
        initialQuota={quotaFixture}
        locale="en-US"
        symbol="AAPL"
        onCompleted={completed}
      />,
    );
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Run agent analysis" }));
      await Promise.resolve();
    });
    expect(screen.getByText("Queued")).toBeVisible();

    for (const state of states) {
      await act(() => vi.advanceTimersByTimeAsync(2_000));
      expect(
        screen.getByText(
          analysisCopy.en.states[state as keyof typeof analysisCopy.en.states],
        ),
      ).toBeVisible();
    }
    expect(completed).toHaveBeenCalledWith(
      intelligenceFixture,
      expect.objectContaining({ remaining: 1 }),
    );
  });

  it("renders the guest daily-limit reset and sign-in action", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json({ code: "AGENT_DAILY_QUOTA_EXCEEDED" }, { status: 429 }),
    );

    render(
      <AnalysisControl
        copy={analysisCopy.en}
        initialQuota={{ ...quotaFixture, used: 2, remaining: 0 }}
        locale="en-US"
        symbol="AAPL"
        onCompleted={vi.fn()}
      />,
    );
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Run agent analysis" }));
      await Promise.resolve();
    });

    expect(screen.getByText(/Daily allowance used/)).toBeVisible();
    expect(screen.getByRole("link", { name: "Sign in for 10 daily analyses" })).toBeVisible();
  });

  it("applies a refunded quota update without resetting job state", () => {
    const view = render(
      <AnalysisControl
        copy={analysisCopy.en}
        initialQuota={{ ...quotaFixture, used: 1, remaining: 1 }}
        locale="en-US"
        symbol="AAPL"
        onCompleted={vi.fn()}
      />,
    );
    expect(screen.getByText("1 daily analyses remaining")).toBeVisible();

    view.rerender(
      <AnalysisControl
        copy={analysisCopy.en}
        initialQuota={{ ...quotaFixture, used: 0, remaining: 2 }}
        locale="en-US"
        symbol="AAPL"
        onCompleted={vi.fn()}
      />,
    );

    expect(screen.getByText("2 daily analyses remaining")).toBeVisible();
  });

  it("retries an eligible failed job once", async () => {
    const failedJob = {
      ...jobFixture,
      state: "failed",
      current_step: "analyzing",
      error_code: "INTELLIGENCE_GENERATION_FAILED",
    };
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        Response.json({
          status: "active_job",
          job: failedJob,
          snapshot_id: null,
          quota: quotaFixture,
        }),
      )
      .mockResolvedValueOnce(
        Response.json({ ...jobFixture, attempt_count: 1 }),
      );

    render(
      <AnalysisControl
        copy={analysisCopy.en}
        initialQuota={quotaFixture}
        locale="en-US"
        symbol="AAPL"
        onCompleted={vi.fn()}
      />,
    );
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Run agent analysis" }));
      await Promise.resolve();
    });
    expect(screen.getByText("Analysis failed")).toBeVisible();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Retry analysis" }));
      await Promise.resolve();
    });

    expect(screen.getByText("Queued")).toBeVisible();
    expect(fetchMock).toHaveBeenLastCalledWith(
      `/api/research/jobs/${jobFixture.id}/retry`,
      expect.objectContaining({ method: "POST" }),
    );
  });
});
