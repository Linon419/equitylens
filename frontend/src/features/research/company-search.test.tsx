import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CompanySearch } from "./company-search";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const copy = {
  label: "Search companies",
  placeholder: "Ticker or company name",
  loading: "Searching…",
  empty: "No companies found",
  error: "Search unavailable",
};

describe("CompanySearch", () => {
  beforeEach(() => vi.useFakeTimers());

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.useRealTimers();
    push.mockReset();
  });

  it("debounces a query and opens the keyboard-selected company", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json({
        items: [{ symbol: "AAPL", name: "Apple Inc.", exchange: "NASDAQ" }],
        count: 1,
      }),
    );
    render(<CompanySearch copy={copy} locale="en-US" />);

    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "app" },
    });
    await act(() => vi.advanceTimersByTimeAsync(249));
    expect(fetchMock).not.toHaveBeenCalled();
    await act(() => vi.advanceTimersByTimeAsync(1));
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/research/companies/search?q=app&limit=8",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(screen.getByRole("option", { name: /Apple Inc./ })).toBeVisible();

    fireEvent.keyDown(screen.getByRole("combobox"), { key: "ArrowDown" });
    fireEvent.keyDown(screen.getByRole("combobox"), { key: "Enter" });
    expect(push).toHaveBeenCalledWith("/en-US/companies/AAPL");
  });

  it("requires two characters and exposes empty and error states", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(Response.json({ items: [], count: 0 }))
      .mockResolvedValueOnce(new Response(null, { status: 503 }));
    render(<CompanySearch copy={copy} locale="en-US" />);
    const input = screen.getByRole("combobox");

    fireEvent.change(input, { target: { value: "a" } });
    await act(() => vi.advanceTimersByTimeAsync(300));
    expect(fetchMock).not.toHaveBeenCalled();
    fireEvent.change(input, { target: { value: "ap" } });
    await act(() => vi.advanceTimersByTimeAsync(250));
    expect(screen.getByText("No companies found")).toBeVisible();

    fireEvent.change(input, { target: { value: "msft" } });
    await act(() => vi.advanceTimersByTimeAsync(250));
    expect(screen.getByText("Search unavailable")).toBeVisible();
  });

  it("supports mouse selection and Escape", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      Response.json({
        items: [{ symbol: "MSFT", name: "Microsoft", exchange: "NASDAQ" }],
        count: 1,
      }),
    );
    render(<CompanySearch copy={copy} locale="en-US" />);

    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "micro" },
    });
    await act(() => vi.advanceTimersByTimeAsync(250));
    fireEvent.mouseDown(screen.getByRole("option", { name: /Microsoft/ }));
    expect(push).toHaveBeenCalledWith("/en-US/companies/MSFT");

    push.mockReset();
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "soft" },
    });
    await act(() => vi.advanceTimersByTimeAsync(250));
    expect(screen.getByRole("listbox")).toBeVisible();
    fireEvent.keyDown(screen.getByRole("combobox"), { key: "Escape" });
    expect(screen.queryByRole("listbox")).toBeNull();
  });
});
