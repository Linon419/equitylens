import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import Dashboard from "./page";

vi.mock("next/navigation", () => ({ notFound: () => undefined }));

describe("localized dashboard shell", () => {
  it("renders the English onboarding state", async () => {
    render(await Dashboard({ params: Promise.resolve({ lang: "en-US" }) }));

    expect(
      screen.getByRole("heading", { name: "Your research starts here." }),
    ).toBeInTheDocument();
  });

  it("renders the Chinese onboarding state", async () => {
    render(await Dashboard({ params: Promise.resolve({ lang: "zh-CN" }) }));

    expect(
      screen.getByRole("heading", {
        name: "从这里开始你的公司研究。",
      }),
    ).toBeInTheDocument();
  });
});
