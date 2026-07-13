"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";

import { LanguageSwitcher } from "@/components/language-switcher";
import { useSession } from "@/components/session-provider";
import type { Locale } from "@/lib/i18n";

type Copy = {
  dashboard: string;
  settings: string;
  signOut: string;
  loading: string;
};

export function AppShell({
  children,
  copy,
  languageLabel,
  locale,
}: {
  children: React.ReactNode;
  copy: Copy;
  languageLabel: string;
  locale: Locale;
}) {
  const router = useRouter();
  const { loading, user } = useSession();

  async function signOut() {
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } finally {
      router.replace(`/${locale}`);
    }
  }

  if (loading || !user) {
    return <main className="session-loading">{copy.loading}</main>;
  }

  return (
    <div className="app-frame">
      <header className="app-header">
        <a className="wordmark" href={`/${locale}/dashboard`}>
          <span className="wordmark__seal">E</span>
          <span>EquityLens</span>
        </a>
        <nav aria-label={copy.dashboard}>
          <a href={`/${locale}/dashboard`}>{copy.dashboard}</a>
          <a href={`/${locale}/settings`}>{copy.settings}</a>
        </nav>
        <div className="app-header__account">
          {user.avatar_url ? (
            <Image
              alt=""
              className="app-header__avatar"
              height={32}
              src={user.avatar_url}
              unoptimized
              width={32}
            />
          ) : null}
          <span className="app-header__name">
            {user.full_name ?? user.email}
          </span>
          <LanguageSwitcher
            authenticated
            locale={locale}
            label={languageLabel}
          />
          <button type="button" onClick={signOut}>
            {copy.signOut}
          </button>
        </div>
      </header>
      <main className="app-content">{children}</main>
    </div>
  );
}
