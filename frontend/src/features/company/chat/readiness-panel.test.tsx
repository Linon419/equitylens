import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { companyPageCopy } from "../copy";
import { ReadinessPanel } from "./readiness-panel";

describe("ReadinessPanel", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("shows independent resources and prepares the filing index without chat quota", async () => {
    const user = userEvent.setup();
    const onRefresh = vi.fn();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json({ status: "ready", job: null, filing_id: "filing-1" }),
    );
    render(
      <ReadinessPanel
        copy={companyPageCopy.en.chat}
        onNavigate={vi.fn()}
        onRefresh={onRefresh}
        readiness={{
          company_symbol: "AAPL",
          intelligence: { state: "ready", action: null },
          filing_text: { state: "ready", action: null },
          filing_index: { state: "missing", action: "filing_index" },
          supply_chain_graph: { state: "failed", action: "supply_chain_graph" },
          web_recency: { state: "ready", action: null },
        }}
        symbol="AAPL"
      />,
    );

    await user.click(screen.getByText(companyPageCopy.en.chat.readiness.title));
    expect(screen.getByText(companyPageCopy.en.chat.readiness.resources.intelligence)).toBeVisible();
    expect(screen.getByText(companyPageCopy.en.chat.readiness.states.failed)).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: companyPageCopy.en.chat.readiness.prepareIndex }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/research/companies/AAPL/chat-index/sync",
      expect.objectContaining({ method: "POST" }),
    );
    expect(onRefresh).toHaveBeenCalledOnce();
    expect(screen.getByText(companyPageCopy.en.chat.readiness.zeroQuota)).toBeVisible();
  });
});
