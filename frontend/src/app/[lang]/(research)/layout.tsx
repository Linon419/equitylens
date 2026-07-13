import { notFound } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { SessionProvider } from "@/components/session-provider";
import { getDictionary } from "@/dictionaries";
import { isLocale } from "@/lib/i18n";

export default async function ResearchLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!isLocale(lang)) notFound();
  const copy = getDictionary(lang);

  return (
    <SessionProvider locale={lang} required={false}>
      <AppShell
        copy={{ ...copy.app.nav, loading: copy.app.loading }}
        languageLabel={copy.language}
        locale={lang}
        variant="research"
      >
        {children}
      </AppShell>
    </SessionProvider>
  );
}
