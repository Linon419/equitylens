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
  it("renders English Google login copy", async () => {
    render(
      await LoginPage({
        params: Promise.resolve({ lang: "en-US" }),
        searchParams: Promise.resolve({}),
      }),
    );

    expect(
      screen.getByRole("heading", { name: "Start with the source." }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Continue with Google" }),
    ).toBeInTheDocument();
  });

  it("renders Chinese Google login copy", async () => {
    render(
      await LoginPage({
        params: Promise.resolve({ lang: "zh-CN" }),
        searchParams: Promise.resolve({}),
      }),
    );

    expect(
      screen.getByRole("heading", { name: "从原始资料开始研究。" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "使用 Google 继续" }),
    ).toBeInTheDocument();
  });
});
