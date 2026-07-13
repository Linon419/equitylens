import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, Newsreader } from "next/font/google";
import { notFound } from "next/navigation";

import { getDictionary } from "@/dictionaries";
import { isLocale, locales } from "@/lib/i18n";
import "../globals.css";

const bodyFont = IBM_Plex_Sans({
  subsets: ["latin"],
  variable: "--font-body",
});
const displayFont = Newsreader({
  subsets: ["latin"],
  variable: "--font-display",
});
const monoFont = IBM_Plex_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "Ledgerly — US Equity Research",
  description: "Traceable company, filing, financial, and valuation research.",
};

export function generateStaticParams() {
  return locales.map((lang) => ({ lang }));
}

export default async function LocaleLayout({
  children,
  params,
}: Readonly<{
  children: React.ReactNode;
  params: Promise<{ lang: string }>;
}>) {
  const { lang } = await params;
  if (!isLocale(lang)) {
    notFound();
  }
  const dictionary = getDictionary(lang);

  return (
    <html lang={lang}>
      <body
        className={`${bodyFont.variable} ${displayFont.variable} ${monoFont.variable}`}
      >
        <span className="sr-only">{dictionary.metadata.description}</span>
        {children}
      </body>
    </html>
  );
}
