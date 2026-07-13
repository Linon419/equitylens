"use client";

import { useRouter } from "next/navigation";
import Script from "next/script";
import { useCallback, useEffect, useRef, useState } from "react";

import type { Locale } from "@/lib/i18n";

type Props = {
  clientId: string;
  errorMessages: {
    accountLink: string;
    disabled: string;
    generic: string;
  };
  label: string;
  locale: Locale;
  returnTo: string;
};

export function GoogleSignInButton({
  clientId,
  errorMessages,
  label,
  locale,
  returnTo,
}: Props) {
  const router = useRouter();
  const target = useRef<HTMLDivElement>(null);
  const [csrfToken, setCsrfToken] = useState<string | null>(null);
  const [scriptReady, setScriptReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function loadCsrf() {
      try {
        const response = await fetch("/api/auth/csrf", { cache: "no-store" });
        const payload = await response.json();
        if (!response.ok || typeof payload.token !== "string") {
          throw new Error("Invalid CSRF response");
        }
        if (active) {
          setCsrfToken(payload.token);
        }
      } catch {
        if (active) {
          setError(errorMessages.generic);
        }
      }
    }

    void loadCsrf();
    return () => {
      active = false;
    };
  }, [errorMessages.generic]);

  const exchangeCredential = useCallback(
    async ({ credential }: GoogleCredentialResponse) => {
      if (!csrfToken) {
        return;
      }
      setError(null);
      try {
        const response = await fetch("/api/auth/google/callback", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            credential,
            csrf_token: csrfToken,
            preferred_locale: locale,
          }),
        });
        if (!response.ok) {
          const payload = await response.json().catch(() => ({ code: "" }));
          const message = {
            AUTH_ACCOUNT_DISABLED: errorMessages.disabled,
            AUTH_ACCOUNT_LINK_REQUIRED: errorMessages.accountLink,
          }[payload.code as string];
          setError(message ?? errorMessages.generic);
          return;
        }
        router.replace(returnTo);
      } catch {
        setError(errorMessages.generic);
      }
    },
    [csrfToken, errorMessages, locale, returnTo, router],
  );

  useEffect(() => {
    if (!scriptReady || !csrfToken || !target.current || !window.google) {
      return;
    }
    target.current.replaceChildren();
    window.google.accounts.id.initialize({
      client_id: clientId,
      callback: exchangeCredential,
    });
    window.google.accounts.id.renderButton(target.current, {
      locale,
      shape: "rectangular",
      size: "large",
      text: "continue_with",
      theme: "outline",
      width: 320,
    });
  }, [clientId, csrfToken, exchangeCredential, locale, scriptReady]);

  return (
    <div className="google-login">
      <Script
        src="https://accounts.google.com/gsi/client"
        strategy="afterInteractive"
        onError={() => setError(errorMessages.generic)}
        onReady={() => setScriptReady(true)}
      />
      <span className="sr-only">{label}</span>
      <div aria-label={label} ref={target} />
      {error ? (
        <p className="auth-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
