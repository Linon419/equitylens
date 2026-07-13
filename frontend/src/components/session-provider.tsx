"use client";

import { usePathname, useRouter } from "next/navigation";
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import type { AuthUser } from "@/lib/auth/types";
import type { Locale } from "@/lib/i18n";

type SessionValue = { user: AuthUser | null; loading: boolean };
const SessionContext = createContext<SessionValue | null>(null);

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) {
    throw new Error("useSession requires SessionProvider");
  }
  return value;
}

export function SessionProvider({
  children,
  locale,
}: {
  children: React.ReactNode;
  locale: Locale;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    const loginPath = `/${locale}/login?returnTo=${encodeURIComponent(pathname)}`;

    async function load(attempt = 0): Promise<void> {
      try {
        const response = await fetch("/api/auth/me", { cache: "no-store" });
        if (response.status === 409 && attempt === 0) {
          await new Promise((resolve) => window.setTimeout(resolve, 150));
          if (active) {
            return load(1);
          }
          return;
        }
        if (!response.ok) {
          if (active) {
            router.replace(loginPath);
          }
          return;
        }
        const current = (await response.json()) as AuthUser;
        if (active) {
          setUser(current);
          setLoading(false);
        }
      } catch {
        if (active) {
          router.replace(loginPath);
        }
      }
    }

    void load();
    return () => {
      active = false;
    };
  }, [locale, pathname, router]);

  const value = useMemo(() => ({ user, loading }), [loading, user]);
  return (
    <SessionContext.Provider value={value}>
      {children}
    </SessionContext.Provider>
  );
}
