import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import Home from "./page";

vi.mock("next/navigation", () => ({
  notFound: () => undefined,
  usePathname: () => "/en-US",
  useRouter: () => ({ replace: () => undefined }),
}));

describe("localized home page", () => {
  it("renders the English research proposition", async () => {
    render(
      await Home({ params: Promise.resolve({ lang: "en-US" }) }),
    );

    expect(
      screen.getByRole("heading", { name: "See the business behind the ticker." }),
    ).toBeInTheDocument();
    expect(screen.getByText("US Equity Research")).toBeInTheDocument();
  });

  it("renders the Chinese research proposition", async () => {
    render(
      await Home({ params: Promise.resolve({ lang: "zh-CN" }) }),
    );

    expect(
      screen.getByRole("heading", { name: "看懂股票代码背后的生意。" }),
    ).toBeInTheDocument();
    expect(screen.getByText("美股投研知识库")).toBeInTheDocument();
  });
});
