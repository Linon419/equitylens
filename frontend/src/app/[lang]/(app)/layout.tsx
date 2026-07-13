import { notFound } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { SessionProvider } from "@/components/session-provider";
import { getDictionary } from "@/dictionaries";
import { isLocale } from "@/lib/i18n";

export default async function ProtectedLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!isLocale(lang)) {
    notFound();
  }
  const copy = getDictionary(lang);

  return (
    <SessionProvider locale={lang}>
      <AppShell
        copy={{ ...copy.app.nav, loading: copy.app.loading }}
        languageLabel={copy.language}
        locale={lang}
      >
        {children}
      </AppShell>
    </SessionProvider>
  );
}
