import { describe, expect, it, vi } from "vitest";

import RootPage from "./page";

const { redirect } = vi.hoisted(() => ({ redirect: vi.fn() }));

vi.mock("next/navigation", () => ({ redirect }));

describe("root page", () => {
  it("redirects to the default locale", () => {
    RootPage();

    expect(redirect).toHaveBeenCalledWith("/en-US");
  });
});
