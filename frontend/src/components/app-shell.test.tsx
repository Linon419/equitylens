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
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
vi.mock("@/components/session-provider", () => ({
  useSession: () => ({
    loading: false,
    user: {
      email: "investor@example.com",
      full_name: "Investor",
      avatar_url: null,
    },
  }),
}));
vi.mock("@/components/language-switcher", () => ({
  LanguageSwitcher: () => <span>language</span>,
}));

describe("AppShell", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    replace.mockReset();
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
  });
});
