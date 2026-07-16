import { notFound } from "next/navigation";

import { BrandMark } from "@/components/brand-mark";
import { GoogleSignInButton } from "@/components/google-sign-in-button";
import { LanguageSwitcher } from "@/components/language-switcher";
import { getDictionary } from "@/dictionaries";
import { safeReturnPath } from "@/lib/auth/security";
import { isLocale } from "@/lib/i18n";

type Props = {
  params: Promise<{ lang: string }>;
  searchParams: Promise<{ returnTo?: string }>;
};

export default async function LoginPage({ params, searchParams }: Props) {
  const { lang } = await params;
  if (!isLocale(lang)) {
    notFound();
  }
  const copy = getDictionary(lang);
  const query = await searchParams;
  const returnTo = safeReturnPath(query.returnTo, `/${lang}/dashboard`);
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
  if (!clientId) {
    throw new Error("NEXT_PUBLIC_GOOGLE_CLIENT_ID is required");
  }

  return (
    <main className="auth-page">
      <div className="ambient-grid" aria-hidden="true" />
      <header className="auth-masthead">
        <a className="wordmark" href={`/${lang}`}>
          <BrandMark />
          <span>EquityLens</span>
        </a>
        <LanguageSwitcher locale={lang} label={copy.language} />
      </header>
      <section className="auth-panel">
        <div className="auth-panel__copy">
          <p className="eyebrow">{copy.auth.eyebrow}</p>
          <h1>{copy.auth.title}</h1>
          <p>{copy.auth.description}</p>
        </div>
        <div className="auth-panel__action">
          <p className="auth-panel__index">{copy.auth.accessIndex}</p>
          <a className="auth-panel__guest" href={returnTo}>
            <span>{copy.auth.guest}</span>
            <span aria-hidden="true">→</span>
          </a>
          <p className="auth-panel__guest-hint">{copy.auth.guestHint}</p>
          <div className="auth-panel__divider" role="separator">
            <span>{copy.auth.accountDivider}</span>
          </div>
          <GoogleSignInButton
            clientId={clientId}
            errorMessages={{
              accountLink: copy.auth.accountLinkError,
              disabled: copy.auth.disabledError,
              generic: copy.auth.genericError,
            }}
            label={copy.auth.google}
            locale={lang}
            returnTo={returnTo}
          />
          <p className="auth-panel__privacy">{copy.auth.privacy}</p>
          <a className="auth-panel__back" href={`/${lang}`}>
            <span aria-hidden="true">←</span> {copy.auth.back}
          </a>
        </div>
      </section>
    </main>
  );
}
