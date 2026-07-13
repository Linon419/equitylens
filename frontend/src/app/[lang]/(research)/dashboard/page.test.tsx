import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import Dashboard from "./page";

vi.mock("next/navigation", () => ({ notFound: () => undefined }));
vi.mock("@/features/research/company-search", () => ({
  CompanySearch: ({ copy }: { copy: { label: string } }) => (
    <input aria-label={copy.label} />
  ),
}));
vi.mock("@/features/research/watchlist", () => ({
  Watchlist: ({ copy }: { copy: { title: string } }) => <h2>{copy.title}</h2>,
}));

describe("public research dashboard", () => {
  it("renders the English product promise and workflow", async () => {
    render(await Dashboard({ params: Promise.resolve({ lang: "en-US" }) }));

    expect(
      screen.getByRole("heading", {
        name: "Understand the company behind the ticker.",
      }),
    ).toBeVisible();
    expect(screen.getByRole("textbox", { name: "Search companies" })).toBeVisible();
    expect(screen.getByText("Core business")).toBeVisible();
    expect(screen.getByText("Value chain")).toBeVisible();
    expect(screen.getByText("Source evidence")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Watchlist" })).toBeVisible();
  });

  it("renders the Chinese product promise", async () => {
    render(await Dashboard({ params: Promise.resolve({ lang: "zh-CN" }) }));

    expect(
      screen.getByRole("heading", { name: "看懂股票代码背后的公司。" }),
    ).toBeVisible();
    expect(screen.getByRole("textbox", { name: "搜索公司" })).toBeVisible();
  });
});
