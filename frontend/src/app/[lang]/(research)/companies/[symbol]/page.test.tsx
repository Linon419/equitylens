import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const notFound = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ notFound }));
vi.mock("@/features/company/company-page", () => ({
  CompanyPage: ({ symbol }: { symbol: string }) => <h1>{symbol}</h1>,
}));

import CompanyRoute from "./page";

describe("company research route", () => {
  it("normalizes a valid symbol", async () => {
    render(
      await CompanyRoute({
        params: Promise.resolve({ lang: "en-US", symbol: "aapl" }),
      }),
    );

    expect(screen.getByRole("heading", { name: "AAPL" })).toBeVisible();
  });

  it("rejects an invalid symbol before rendering", async () => {
    await CompanyRoute({
      params: Promise.resolve({ lang: "en-US", symbol: "../auth" }),
    });

    expect(notFound).toHaveBeenCalled();
  });
});
