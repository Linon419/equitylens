import { notFound } from "next/navigation";

import { getDictionary } from "@/dictionaries";
import { CompanyPage } from "@/features/company/company-page";
import { isLocale } from "@/lib/i18n";

const SYMBOL_PATTERN = /^[A-Za-z][A-Za-z0-9.-]{0,9}$/;

export default async function CompanyRoute({
  params,
}: {
  params: Promise<{ lang: string; symbol: string }>;
}) {
  const { lang, symbol } = await params;
  if (!isLocale(lang) || !SYMBOL_PATTERN.test(symbol)) notFound();

  return (
    <CompanyPage
      copy={getDictionary(lang).app.company}
      locale={lang}
      symbol={symbol.toUpperCase()}
    />
  );
}
