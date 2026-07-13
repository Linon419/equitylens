import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LanguageSwitcher } from "./language-switcher";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/en-US/company/AAPL",
  useRouter: () => ({ replace }),
}));

describe("LanguageSwitcher", () => {
  beforeEach(() => {
    replace.mockClear();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("preserves the current path while changing the locale", () => {
    render(<LanguageSwitcher locale="en-US" label="Language" />);

    fireEvent.change(screen.getByRole("combobox", { name: "Language" }), {
      target: { value: "zh-CN" },
    });

    expect(replace).toHaveBeenCalledWith("/zh-CN/company/AAPL");
    expect(document.cookie).toContain("locale=zh-CN");
  });

  it("persists an authenticated locale preference", () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(Response.json({}));
    render(
      <LanguageSwitcher
        authenticated
        locale="en-US"
        label="Language"
      />,
    );

    fireEvent.change(screen.getByRole("combobox", { name: "Language" }), {
      target: { value: "zh-CN" },
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/preferences",
      expect.objectContaining({ method: "PATCH" }),
    );
  });
});
