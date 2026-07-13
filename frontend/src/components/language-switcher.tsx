"use client";

import { usePathname, useRouter } from "next/navigation";

import {
  localeCookieName,
  locales,
  type Locale,
} from "@/lib/i18n";

type LanguageSwitcherProps = {
  locale: Locale;
  label: string;
};

export function LanguageSwitcher({ locale, label }: LanguageSwitcherProps) {
  const pathname = usePathname();
  const router = useRouter();

  function changeLocale(nextLocale: Locale) {
    document.cookie = `${localeCookieName}=${nextLocale}; path=/; max-age=31536000; samesite=lax`;
    const segments = pathname.split("/");
    segments[1] = nextLocale;
    router.replace(segments.join("/") || `/${nextLocale}`);
  }

  return (
    <label className="language-switcher">
      <span className="sr-only">{label}</span>
      <span aria-hidden="true" className="language-switcher__mark">
        文/A
      </span>
      <select
        aria-label={label}
        value={locale}
        onChange={(event) => changeLocale(event.target.value as Locale)}
      >
        {locales.map((supportedLocale) => (
          <option key={supportedLocale} value={supportedLocale}>
            {supportedLocale === "en-US" ? "English" : "简体中文"}
          </option>
        ))}
      </select>
    </label>
  );
}
