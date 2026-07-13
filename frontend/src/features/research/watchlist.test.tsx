import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Watchlist } from "./watchlist";

const session = vi.hoisted(() => ({ user: null as object | null }));
vi.mock("@/components/session-provider", () => ({ useSession: () => session }));

const copy = {
  eyebrow: "Saved research",
  title: "Watchlist",
  guest: "Sign in to build your watchlist.",
  signIn: "Sign in",
  loading: "Loading watchlist…",
  empty: "No saved companies yet.",
  error: "Watchlist unavailable.",
  addLabel: "Add ticker",
  add: "Add",
  remove: "Remove",
  price: "Price",
  pe: "P/E",
  added: "Company added.",
  removed: "Company removed.",
};

describe("Watchlist", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    session.user = null;
  });

  it("shows a guest sign-in action without requesting a watchlist", () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");

    render(<Watchlist copy={copy} locale="en-US" />);

    expect(screen.getByRole("link", { name: "Sign in" })).toBeVisible();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("renders a signed-in investor's watchlist and removes a company", async () => {
    session.user = { email: "investor@example.com" };
    const user = userEvent.setup();
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        Response.json({
          items: [
            {
              symbol: "AAPL",
              name: "Apple Inc.",
              exchange: "NASDAQ",
              price: "210.50",
              trailing_pe: "31.2",
              added_at: "2026-07-13T00:00:00Z",
            },
          ],
          count: 1,
        }),
      )
      .mockResolvedValueOnce(
        Response.json({ symbol: "AAPL", in_watchlist: false }),
      );

    render(<Watchlist copy={copy} locale="en-US" />);
    expect(await screen.findByText("Apple Inc.")).toBeVisible();
    await user.click(screen.getByRole("button", { name: /Remove AAPL/ }));

    await waitFor(() => expect(screen.queryByText("Apple Inc.")).toBeNull());
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/research/watchlist/AAPL",
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("rolls back an optimistic add after an upstream error", async () => {
    session.user = { email: "investor@example.com" };
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(Response.json({ items: [], count: 0 }))
      .mockResolvedValueOnce(new Response(null, { status: 503 }));

    render(<Watchlist copy={copy} locale="en-US" />);
    expect(await screen.findByText("No saved companies yet.")).toBeVisible();
    await user.type(screen.getByRole("textbox", { name: "Add ticker" }), "nvda");
    await user.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() => expect(screen.getByText("Watchlist unavailable.")).toBeVisible());
    expect(screen.queryByText("NVDA")).toBeNull();
  });
});
