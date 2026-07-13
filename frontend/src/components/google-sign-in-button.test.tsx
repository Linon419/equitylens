import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GoogleSignInButton } from "./google-sign-in-button";

vi.mock("next/script", () => ({
  default: ({ onReady }: { onReady: () => void }) => (
    <button onClick={onReady}>load-google</button>
  ),
}));

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));

function installGoogle() {
  let googleCallback: (response: { credential: string }) => void = () =>
    undefined;
  Object.assign(window, {
    google: {
      accounts: {
        id: {
          initialize: vi.fn(
            ({ callback }: { callback: typeof googleCallback }) => {
              googleCallback = callback;
            },
          ),
          renderButton: vi.fn(),
        },
      },
    },
  });
  return () => googleCallback({ credential: "google-token" });
}

const props = {
  clientId: "client-id",
  errorMessages: {
    accountLink: "Link this account first",
    disabled: "Account disabled",
    generic: "Try again",
  },
  label: "Continue with Google",
  locale: "en-US" as const,
  returnTo: "/en-US/dashboard",
};

describe("GoogleSignInButton", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    replace.mockReset();
  });

  it("exchanges the Google credential and redirects internally", async () => {
    const completeGoogleSignIn = installGoogle();
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(Response.json({ token: "csrf-token" }))
      .mockResolvedValueOnce(Response.json({ user: { id: 1 } }));

    render(<GoogleSignInButton {...props} />);
    fireEvent.click(screen.getByText("load-google"));
    await waitFor(() =>
      expect(window.google.accounts.id.initialize).toHaveBeenCalled(),
    );
    completeGoogleSignIn();

    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith("/en-US/dashboard"),
    );
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/auth/google/callback",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("shows a stable account-linking error", async () => {
    const completeGoogleSignIn = installGoogle();
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(Response.json({ token: "csrf-token" }))
      .mockResolvedValueOnce(
        Response.json(
          { code: "AUTH_ACCOUNT_LINK_REQUIRED" },
          { status: 409 },
        ),
      );

    render(<GoogleSignInButton {...props} />);
    fireEvent.click(screen.getByText("load-google"));
    await waitFor(() =>
      expect(window.google.accounts.id.initialize).toHaveBeenCalled(),
    );
    completeGoogleSignIn();

    expect(
      await screen.findByRole("alert", { name: "" }),
    ).toHaveTextContent("Link this account first");
  });
});
