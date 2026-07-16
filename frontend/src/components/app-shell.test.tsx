import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "./app-shell";

const replace = vi.fn();
const session = vi.hoisted(() => ({
  loading: false,
  user: {
    id: 1,
    email: "investor@example.com",
    full_name: "Investor",
    avatar_url: null,
    preferred_locale: "en-US" as const,
    created_at: "2026-07-13T00:00:00Z",
  } as {
    id: number;
    email: string;
    full_name: string | null;
    avatar_url: string | null;
    preferred_locale: "en-US";
    created_at: string;
  } | null,
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));
vi.mock("@/components/session-provider", () => ({
  useSession: () => session,
}));
vi.mock("@/components/language-switcher", () => ({
  LanguageSwitcher: ({ authenticated }: { authenticated?: boolean }) => (
    <span>{authenticated ? "account language" : "guest language"}</span>
  ),
}));

describe("AppShell", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    replace.mockReset();
    session.user = {
      id: 1,
      email: "investor@example.com",
      full_name: "Investor",
      avatar_url: null,
      preferred_locale: "en-US",
      created_at: "2026-07-13T00:00:00Z",
    };
  });

  it("logs out and returns to the localized home page", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, { status: 204 }),
    );
    render(
      <AppShell
        copy={{
          dashboard: "Dashboard",
          settings: "Settings",
          signOut: "Sign out",
          signIn: "Sign in",
          loading: "Loading",
        }}
        languageLabel="Language"
        locale="en-US"
      >
        <p>content</p>
      </AppShell>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/en-US"));
    expect(screen.queryByRole("link", { name: "Dashboard" })).toBeNull();
    expect(screen.getByRole("link", { name: "Settings" })).toBeVisible();
  });

  it("renders guest navigation, sign-in, and language controls", () => {
    session.user = null;

    render(
      <AppShell
        copy={{
          dashboard: "Dashboard",
          settings: "Settings",
          signOut: "Sign out",
          signIn: "Sign in",
          loading: "Loading",
        }}
        languageLabel="Language"
        locale="en-US"
      >
        <p>public research</p>
      </AppShell>,
    );

    expect(screen.getByText("public research")).toBeVisible();
    expect(document.querySelector(".wordmark__mark")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Dashboard" })).toBeNull();
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute(
      "href",
      "/en-US/login?returnTo=%2Fen-US%2Fdashboard",
    );
    expect(screen.getByText("guest language")).toBeVisible();
    expect(screen.queryByRole("link", { name: "Settings" })).toBeNull();
  });
});
