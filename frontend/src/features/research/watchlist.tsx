"use client";

import { useEffect, useState } from "react";

import { useSession } from "@/components/session-provider";
import type { Locale } from "@/lib/i18n";
import type {
  WatchlistItem,
  WatchlistResponse,
} from "@/lib/research/types";

type WatchlistCopy = {
  eyebrow: string;
  title: string;
  guest: string;
  signIn: string;
  loading: string;
  empty: string;
  error: string;
  addLabel: string;
  add: string;
  remove: string;
  price: string;
  pe: string;
  added: string;
  removed: string;
};

export function Watchlist({
  copy,
  locale,
}: {
  copy: WatchlistCopy;
  locale: Locale;
}) {
  const { user } = useSession();
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [symbol, setSymbol] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [announcement, setAnnouncement] = useState("");

  useEffect(() => {
    if (!user) return;
    const controller = new AbortController();
    void fetch("/api/research/watchlist", {
      cache: "no-store",
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("watchlist request failed");
        return (await response.json()) as WatchlistResponse;
      })
      .then((payload) => setItems(payload.items))
      .catch((requestError) => {
        if (
          requestError instanceof DOMException &&
          requestError.name === "AbortError"
        ) {
          return;
        }
        setError(true);
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [user]);

  if (!user) {
    return (
      <section className="watchlist-card watchlist-card--guest">
        <p className="watchlist-card__eyebrow">{copy.eyebrow}</p>
        <h2>{copy.title}</h2>
        <p>{copy.guest}</p>
        <a
          className="watchlist-card__sign-in"
          href={`/${locale}/login?returnTo=${encodeURIComponent(`/${locale}/dashboard`)}`}
        >
          {copy.signIn} <span aria-hidden="true">↗</span>
        </a>
      </section>
    );
  }

  async function addCompany(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = symbol.trim().toUpperCase();
    if (!/^[A-Z][A-Z0-9.-]{0,9}$/.test(normalized)) return;
    if (items.some((item) => item.symbol === normalized)) {
      setSymbol("");
      return;
    }
    const previous = items;
    const optimistic: WatchlistItem = {
      symbol: normalized,
      name: normalized,
      exchange: null,
      price: null,
      trailing_pe: null,
      added_at: new Date().toISOString(),
    };
    setItems([optimistic, ...items]);
    setSymbol("");
    setError(false);
    try {
      const response = await fetch(`/api/research/watchlist/${normalized}`, {
        method: "POST",
      });
      if (!response.ok) throw new Error("watchlist add failed");
      setAnnouncement(copy.added);
    } catch {
      setItems(previous);
      setError(true);
    }
  }

  async function removeCompany(item: WatchlistItem) {
    const previous = items;
    setItems(items.filter((candidate) => candidate.symbol !== item.symbol));
    setError(false);
    try {
      const response = await fetch(`/api/research/watchlist/${item.symbol}`, {
        method: "DELETE",
      });
      if (!response.ok) throw new Error("watchlist delete failed");
      setAnnouncement(copy.removed);
    } catch {
      setItems(previous);
      setError(true);
    }
  }

  return (
    <section className="watchlist-card">
      <header className="watchlist-card__header">
        <div>
          <p className="watchlist-card__eyebrow">{copy.eyebrow}</p>
          <h2>{copy.title}</h2>
        </div>
        <form className="watchlist-card__form" onSubmit={addCompany}>
          <label className="sr-only" htmlFor="watchlist-symbol">
            {copy.addLabel}
          </label>
          <input
            id="watchlist-symbol"
            aria-label={copy.addLabel}
            maxLength={10}
            placeholder="AAPL"
            value={symbol}
            onChange={(event) => setSymbol(event.target.value)}
          />
          <button type="submit">{copy.add}</button>
        </form>
      </header>
      {loading ? <p role="status">{copy.loading}</p> : null}
      {error ? <p role="alert">{copy.error}</p> : null}
      {!loading && items.length === 0 ? <p>{copy.empty}</p> : null}
      {items.length > 0 ? (
        <div className="watchlist-table">
          <div className="watchlist-table__labels" aria-hidden="true">
            <span>{copy.title}</span>
            <span>{copy.price}</span>
            <span>{copy.pe}</span>
            <span />
          </div>
          <ul>
            {items.map((item) => (
              <li key={item.symbol}>
                <a href={`/${locale}/companies/${item.symbol}`}>
                  <strong>{item.symbol}</strong>
                  <span>{item.name}</span>
                </a>
                <span>{formatPrice(item.price, locale)}</span>
                <span>{item.trailing_pe ? `${item.trailing_pe}×` : "—"}</span>
                <button
                  aria-label={`${copy.remove} ${item.symbol}`}
                  type="button"
                  onClick={() => void removeCompany(item)}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <p aria-live="polite" className="sr-only">
        {announcement}
      </p>
    </section>
  );
}

function formatPrice(value: string | null, locale: Locale): string {
  if (value === null) return "—";
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(Number(value));
}
