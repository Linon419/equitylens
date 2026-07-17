import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const notFound = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ notFound }));
vi.mock("@/features/company/company-page", () => ({
  CompanyPage: ({
    initialCompany,
    symbol,
  }: {
    initialCompany?: { name: string };
    symbol: string;
  }) => <h1>{initialCompany?.name ?? symbol}</h1>,
}));

import CompanyRoute from "./page";

describe("company research route", () => {
  beforeEach(() => {
    notFound.mockReset();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json({
        symbol: "AAPL",
        name: "Apple Inc.",
        exchange: "Nasdaq",
        cik: "0000320193",
        sector: "Technology",
        industry: "Consumer Electronics",
        description: "Apple designs consumer technology products.",
      }),
    );
  });

  afterEach(() => vi.restoreAllMocks());

  it("normalizes a valid symbol and prefills the company", async () => {
    render(
      await CompanyRoute({
        params: Promise.resolve({ lang: "en-US", symbol: "aapl" }),
      }),
    );

    expect(screen.getByRole("heading", { name: "Apple Inc." })).toBeVisible();
    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/companies/AAPL",
      expect.objectContaining({ next: { revalidate: 21_600 } }),
    );
  });

  it("rejects an invalid symbol before rendering", async () => {
    await CompanyRoute({
      params: Promise.resolve({ lang: "en-US", symbol: "../auth" }),
    });

    expect(notFound).toHaveBeenCalled();
  });
});
