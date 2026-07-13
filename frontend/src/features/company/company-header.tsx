"use client";

import { useState } from "react";

import { useSession } from "@/components/session-provider";
import type { Company } from "@/lib/research/types";

export function CompanyHeader({
  company,
  copy,
}: {
  company: Company;
  copy: {
    add: string;
    remove: string;
    companyRecord: string;
    sector: string;
    industry: string;
  };
}) {
  const { user } = useSession();
  const [saved, setSaved] = useState(false);
  const [pending, setPending] = useState(false);

  async function toggleWatchlist() {
    const previous = saved;
    setSaved(!saved);
    setPending(true);
    try {
      const response = await fetch(`/api/research/watchlist/${company.symbol}`, {
        method: previous ? "DELETE" : "POST",
      });
      if (!response.ok) throw new Error("watchlist update failed");
    } catch {
      setSaved(previous);
    } finally {
      setPending(false);
    }
  }

  return (
    <header className="company-header">
      <div className="company-header__identity">
        <p>{copy.companyRecord} / {company.exchange ?? "US"}</p>
        <div className="company-header__ticker">
          <span>{company.symbol}</span>
          <span>{company.cik}</span>
        </div>
        <h1>{company.name}</h1>
        <p className="company-header__description">{company.description}</p>
      </div>
      <dl>
        <div><dt>{copy.sector}</dt><dd>{company.sector ?? "—"}</dd></div>
        <div><dt>{copy.industry}</dt><dd>{company.industry ?? "—"}</dd></div>
      </dl>
      {user ? (
        <button disabled={pending} type="button" onClick={toggleWatchlist}>
          {saved ? copy.remove : copy.add}
        </button>
      ) : null}
    </header>
  );
}
