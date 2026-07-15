import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import LoginPage from "./page";

vi.mock("@/components/google-sign-in-button", () => ({
  GoogleSignInButton: ({ label }: { label: string }) => (
    <button>{label}</button>
  ),
}));
vi.mock("next/navigation", () => ({
  notFound: () => undefined,
  usePathname: () => "/en-US/login",
  useRouter: () => ({ replace: () => undefined }),
}));

describe("localized login page", () => {
  it("renders English Google and guest access with a safe default", async () => {
    render(
      await LoginPage({
        params: Promise.resolve({ lang: "en-US" }),
        searchParams: Promise.resolve({
          returnTo: "https://malicious.example/steal-session",
        }),
      }),
    );

    expect(
      screen.getByRole("heading", { name: "Start with the source." }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Continue with Google" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Continue as guest" }),
    ).toHaveAttribute("href", "/en-US/dashboard");
    expect(
      screen.getByText("2 research messages per day · 7-day history"),
    ).toBeInTheDocument();
  });

  it("renders Chinese guest access and preserves a safe return path", async () => {
    render(
      await LoginPage({
        params: Promise.resolve({ lang: "zh-CN" }),
        searchParams: Promise.resolve({
          returnTo: "/zh-CN/companies/AAPL?source=login",
        }),
      }),
    );

    expect(
      screen.getByRole("heading", { name: "从原始资料开始研究。" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "使用 Google 继续" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "以游客身份继续" }),
    ).toHaveAttribute("href", "/zh-CN/companies/AAPL?source=login");
    expect(screen.getByText("每天 2 次研究对话 · 历史保留 7 天")).toBeInTheDocument();
  });
});
