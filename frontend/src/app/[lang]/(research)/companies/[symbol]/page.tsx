import { notFound } from "next/navigation";

import { getDictionary } from "@/dictionaries";
import { CompanyPage } from "@/features/company/company-page";
import { authConfig } from "@/lib/auth/config";
import { isLocale } from "@/lib/i18n";
import { parseResearchResponse, type Company } from "@/lib/research/types";

const SYMBOL_PATTERN = /^[A-Za-z][A-Za-z0-9.-]{0,9}$/;
const COMPANY_REVALIDATE_SECONDS = 6 * 60 * 60;

export default async function CompanyRoute({
  params,
}: {
  params: Promise<{ lang: string; symbol: string }>;
}) {
  const { lang, symbol } = await params;
  if (!isLocale(lang) || !SYMBOL_PATTERN.test(symbol)) notFound();
  const normalizedSymbol = symbol.toUpperCase();
  const initialCompany = await loadInitialCompany(normalizedSymbol);

  return (
    <CompanyPage
      copy={getDictionary(lang).app.company}
      initialCompany={initialCompany}
      key={normalizedSymbol}
      locale={lang}
      symbol={normalizedSymbol}
    />
  );
}

async function loadInitialCompany(symbol: string): Promise<Company | undefined> {
  try {
    const response = await fetch(
      `${authConfig().backendUrl}/api/v1/companies/${encodeURIComponent(symbol)}`,
      {
        headers: { accept: "application/json" },
        next: { revalidate: COMPANY_REVALIDATE_SECONDS },
      },
    );
    if (!response.ok) return undefined;
    return parseResearchResponse("company", await response.json());
  } catch {
    return undefined;
  }
}
