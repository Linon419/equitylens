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
  signIn: string;
  loading: string;
};

export function AppShell({
  children,
  copy,
  languageLabel,
  locale,
  variant = "default",
}: {
  children: React.ReactNode;
  copy: Copy;
  languageLabel: string;
  locale: Locale;
  variant?: "default" | "research";
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

  if (loading) {
    return <main className="session-loading">{copy.loading}</main>;
  }

  return (
    <div className={`app-frame app-frame--${variant}`}>
      <header className="app-header">
        <a className="wordmark" href={`/${locale}/dashboard`}>
          <span className="wordmark__seal">E</span>
          <span>EquityLens</span>
        </a>
        <nav aria-label={copy.dashboard}>
          <a href={`/${locale}/dashboard`}>{copy.dashboard}</a>
          {user ? <a href={`/${locale}/settings`}>{copy.settings}</a> : null}
        </nav>
        <div className="app-header__account">
          {user?.avatar_url ? (
            <Image
              alt=""
              className="app-header__avatar"
              height={32}
              src={user.avatar_url}
              unoptimized
              width={32}
            />
          ) : null}
          {user ? (
            <span className="app-header__name">
              {user.full_name ?? user.email}
            </span>
          ) : null}
          <LanguageSwitcher
            authenticated={Boolean(user)}
            locale={locale}
            label={languageLabel}
          />
          {user ? (
            <button type="button" onClick={signOut}>
              {copy.signOut}
            </button>
          ) : (
            <a
              className="app-header__sign-in"
              href={`/${locale}/login?returnTo=${encodeURIComponent(`/${locale}/dashboard`)}`}
            >
              {copy.signIn}
            </a>
          )}
        </div>
      </header>
      <main className="app-content">{children}</main>
    </div>
  );
}
