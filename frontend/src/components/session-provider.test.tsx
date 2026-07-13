import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SessionProvider, useSession } from "./session-provider";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => "/en-US/dashboard",
  useRouter: () => ({ replace }),
}));

function Probe() {
  const { user } = useSession();
  return <span>{user?.email ?? "loading"}</span>;
}

describe("SessionProvider", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    replace.mockReset();
  });

  it("loads the authenticated user", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json({
        id: 1,
        email: "investor@example.com",
        preferred_locale: "en-US",
      }),
    );

    render(
      <SessionProvider locale="en-US">
        <Probe />
      </SessionProvider>,
    );

    expect(
      await screen.findByText("investor@example.com"),
    ).toBeInTheDocument();
  });

  it("redirects an expired session to localized login", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json({ code: "AUTH_REQUIRED" }, { status: 401 }),
    );

    render(
      <SessionProvider locale="en-US">
        <Probe />
      </SessionProvider>,
    );

    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith(
        "/en-US/login?returnTo=%2Fen-US%2Fdashboard",
      ),
    );
  });
});
