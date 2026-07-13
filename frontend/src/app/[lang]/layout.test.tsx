import { describe, expect, it, vi } from "vitest";

import { generateMetadata } from "./layout";

vi.mock("next/font/google", () => ({
  IBM_Plex_Mono: () => ({ variable: "font-mono" }),
  IBM_Plex_Sans: () => ({ variable: "font-body" }),
  Newsreader: () => ({ variable: "font-display" }),
}));

vi.mock("next/navigation", () => ({
  notFound: () => undefined,
}));

describe("generateMetadata", () => {
  it("uses Chinese metadata for the Chinese route", async () => {
    const metadata = await generateMetadata({
      params: Promise.resolve({ lang: "zh-CN" }),
    });

    expect(metadata.title).toBe("Ledgerly — 美股投研知识库");
    expect(metadata.description).toBe("有据可查的公司、财报、财务与估值研究。");
  });
});
