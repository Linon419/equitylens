import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/components/session-provider", () => ({
  useSession: () => ({ user: null, loading: false }),
}));

import { FinancialTable } from "./financial-table";
import { CompanyPage, companyPageCopy } from "./company-page";
import {
  companyFixture,
  financialsFixture,
  intelligenceFixture,
  marketFixture,
  quotaFixture,
  supplyChainGraphCachedFixture,
} from "./test-fixtures";

describe("CompanyPage", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("loads independent company resources and marks stale market data", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(fetchFixture);

    render(
      <CompanyPage
        copy={companyPageCopy.en}
        locale="en-US"
        symbol="AAPL"
      />,
    );

    expect(await screen.findByRole("heading", { name: "Apple Inc." })).toBeVisible();
    const urls = fetchMock.mock.calls.map(([url]) => String(url));
    expect(urls).toEqual(
      expect.arrayContaining([
        "/api/research/companies/AAPL",
        "/api/research/companies/AAPL/market",
        "/api/research/companies/AAPL/financials",
        "/api/research/companies/AAPL/intelligence?locale=en",
        "/api/research/companies/AAPL/supply-chain-graph?locale=en&evidence=verified%2Cpotential",
        "/api/research/agent-quota",
      ]),
    );
    expect(screen.getByText(/Stale market data/)).toBeVisible();
    expect(screen.getByText(/USD · SEC XBRL Company Facts/)).toBeVisible();
    expect(screen.getByRole("heading", { name: "AI supply-chain graph" })).toBeVisible();
    expect(screen.getByText(supplyChainGraphCachedFixture.snapshot.thesis)).toBeVisible();
  });

  it("renders a dedicated company-not-found state", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (url) =>
      String(url).endsWith("/companies/AAPL")
        ? Response.json({ code: "COMPANY_NOT_FOUND" }, { status: 404 })
        : new Response(null, { status: 503 }),
    );

    render(
      <CompanyPage copy={companyPageCopy.en} locale="en-US" symbol="AAPL" />,
    );

    expect(await screen.findByRole("heading", { name: "Company not found" })).toBeVisible();
  });

  it("preserves financials when intelligence and market are unavailable", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
      const path = String(url);
      if (path.endsWith("/companies/AAPL")) return Response.json(companyFixture);
      if (path.endsWith("/financials")) return Response.json(financialsFixture);
      if (path.endsWith("/agent-quota")) return Response.json(quotaFixture);
      return new Response(null, { status: 404 });
    });

    render(
      <CompanyPage copy={companyPageCopy.en} locale="en-US" symbol="AAPL" />,
    );

    expect(await screen.findByText("Revenue")).toBeVisible();
    await waitFor(() =>
      expect(screen.getAllByText("Data unavailable").length).toBeGreaterThan(0),
    );
    expect(screen.getByText("Run the research agent to build cited intelligence.")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Build this company’s cited market map" })).toBeVisible();
  });

  it("treats a missing graph as an Agent-ready empty state", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
      const path = String(url);
      if (path.endsWith("/companies/AAPL")) return Response.json(companyFixture);
      if (path.endsWith("/market")) return Response.json(marketFixture);
      if (path.endsWith("/financials")) return Response.json(financialsFixture);
      if (path.includes("/intelligence")) return Response.json(intelligenceFixture);
      if (path.endsWith("/agent-quota")) return Response.json(quotaFixture);
      return new Response(null, { status: 404 });
    });

    render(<CompanyPage copy={companyPageCopy.en} locale="en-US" symbol="AAPL" />);

    expect(await screen.findByRole("heading", { name: "AI supply-chain graph" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Generate graph" })).toBeVisible();
    expect(screen.queryByText(companyPageCopy.en.partialLoad)).toBeNull();
  });
});

describe("FinancialTable", () => {
  it("renders four fiscal years plus TTM with metric units", () => {
    render(<FinancialTable data={financialsFixture} locale="en" />);

    expect(
      screen.getAllByRole("columnheader").map((node) => node.textContent),
    ).toEqual(["Metric", "FY 2022", "FY 2023", "FY 2024", "FY 2025", "TTM"]);
    expect(screen.getByText("Revenue")).toBeVisible();
    expect(screen.getByText("Free cash flow")).toBeVisible();
    expect(screen.getByText("USD · SEC XBRL Company Facts")).toBeVisible();
  });

  it("preserves negative values and displays missing values", () => {
    const data = structuredClone(financialsFixture);
    data.series[0].annual = [];
    data.series[0].ttm = null;
    render(<FinancialTable data={data} locale="en" />);

    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/−\$/).length).toBeGreaterThan(0);
  });
});

async function fetchFixture(input: RequestInfo | URL) {
  const url = String(input);
  if (url.endsWith("/companies/AAPL")) return Response.json(companyFixture);
  if (url.endsWith("/market")) return Response.json(marketFixture);
  if (url.endsWith("/financials")) return Response.json(financialsFixture);
  if (url.includes("/intelligence")) return Response.json(intelligenceFixture);
  if (url.includes("/supply-chain-graph")) return Response.json(supplyChainGraphCachedFixture);
  if (url.endsWith("/agent-quota")) return Response.json(quotaFixture);
  return new Response(null, { status: 404 });
}
