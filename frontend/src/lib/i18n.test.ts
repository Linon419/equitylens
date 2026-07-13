import { describe, expect, it } from "vitest";

import { resolveLocale } from "./i18n";

describe("resolveLocale", () => {
  it("prefers a saved locale over the browser language", () => {
    expect(
      resolveLocale({ cookieLocale: "en-US", acceptLanguage: "zh-CN,zh;q=0.9" }),
    ).toBe("en-US");
  });

  it("maps Chinese browser preferences to Simplified Chinese", () => {
    expect(
      resolveLocale({ cookieLocale: null, acceptLanguage: "zh-TW,zh;q=0.9" }),
    ).toBe("zh-CN");
  });

  it("falls back to English", () => {
    expect(
      resolveLocale({ cookieLocale: null, acceptLanguage: "fr-FR,fr;q=0.9" }),
    ).toBe("en-US");
  });
});
