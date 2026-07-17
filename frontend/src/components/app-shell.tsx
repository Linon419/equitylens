"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";

import { BrandMark } from "@/components/brand-mark";
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

  if (loading && variant === "default") {
    return <main className="session-loading">{copy.loading}</main>;
  }

  return (
    <div className={`app-frame app-frame--${variant}`}>
      <header className="app-header">
        <a className="wordmark" href={`/${locale}/dashboard`}>
          <BrandMark />
          <span>EquityLens</span>
        </a>
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
          {user ? (
            <a
              className="app-header__settings"
              href={`/${locale}/settings`}
            >
              {copy.settings}
            </a>
          ) : null}
          <LanguageSwitcher
            authenticated={Boolean(user)}
            locale={locale}
            label={languageLabel}
          />
          {loading ? (
            <span
              aria-label={copy.loading}
              className="app-header__session-placeholder"
              role="status"
            />
          ) : user ? (
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
