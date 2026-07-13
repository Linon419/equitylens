export const locales = ["en-US", "zh-CN"] as const;
export const defaultLocale = "en-US";
export const localeCookieName = "locale";

export type Locale = (typeof locales)[number];

type LocaleSignals = {
  cookieLocale: string | null;
  acceptLanguage: string | null;
};

export function isLocale(value: string): value is Locale {
  return locales.includes(value as Locale);
}

function browserLocale(acceptLanguage: string | null): Locale {
  const preferences = (acceptLanguage ?? "")
    .split(",")
    .map((part) => part.trim().split(";")[0]?.toLowerCase())
    .filter(Boolean);

  if (preferences.some((language) => language.startsWith("zh"))) {
    return "zh-CN";
  }
  if (preferences.some((language) => language.startsWith("en"))) {
    return "en-US";
  }
  return defaultLocale;
}

export function resolveLocale(signals: LocaleSignals): Locale {
  if (signals.cookieLocale && isLocale(signals.cookieLocale)) {
    return signals.cookieLocale;
  }
  return browserLocale(signals.acceptLanguage);
}
