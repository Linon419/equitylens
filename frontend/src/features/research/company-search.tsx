"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useState } from "react";

import type {
  CompanySearchItem,
  CompanySearchResponse,
} from "@/lib/research/types";
import type { Locale } from "@/lib/i18n";

type SearchCopy = {
  label: string;
  placeholder: string;
  loading: string;
  empty: string;
  error: string;
};

export function CompanySearch({
  copy,
  locale,
}: {
  copy: SearchCopy;
  locale: Locale;
}) {
  const router = useRouter();
  const listboxId = useId();
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<CompanySearchItem[]>([]);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [status, setStatus] = useState<
    "idle" | "loading" | "ready" | "error"
  >("idle");
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const normalized = query.trim();
    if (normalized.length < 2) return;

    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        const response = await fetch(
          `/api/research/companies/search?q=${encodeURIComponent(normalized)}&limit=8`,
          { cache: "no-store", signal: controller.signal },
        );
        if (!response.ok) throw new Error("company search failed");
        const payload = (await response.json()) as CompanySearchResponse;
        setItems(payload.items.slice(0, 8));
        setActiveIndex(-1);
        setStatus("ready");
        setOpen(true);
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setItems([]);
        setStatus("error");
        setOpen(true);
      }
    }, 250);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  function selectCompany(item: CompanySearchItem) {
    setOpen(false);
    router.push(`/${locale}/companies/${item.symbol}`);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      setOpen(false);
      return;
    }
    if (!open || items.length === 0) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((index) => Math.min(index + 1, items.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter" && activeIndex >= 0) {
      event.preventDefault();
      selectCompany(items[activeIndex]);
    }
  }

  return (
    <div className="company-search">
      <div className="company-search__label">
        <span>US</span>
        <label htmlFor={`${listboxId}-input`}>{copy.label}</label>
      </div>
      <div className="company-search__control">
        <input
          id={`${listboxId}-input`}
          aria-activedescendant={
            activeIndex >= 0 ? `${listboxId}-${activeIndex}` : undefined
          }
          aria-autocomplete="list"
          aria-controls={listboxId}
          aria-expanded={open}
          aria-label={copy.label}
          autoComplete="off"
          placeholder={copy.placeholder}
          role="combobox"
          value={query}
          onChange={(event) => {
            const nextQuery = event.target.value;
            setQuery(nextQuery);
            setActiveIndex(-1);
            if (nextQuery.trim().length < 2) {
              setItems([]);
              setOpen(false);
              setStatus("idle");
            } else {
              setStatus("loading");
              setOpen(true);
            }
          }}
          onKeyDown={handleKeyDown}
        />
        <span aria-hidden="true" className="company-search__key">
          ↵
        </span>
      </div>
      {open ? (
        <div className="company-search__popover">
          {status === "loading" ? (
            <p role="status">{copy.loading}</p>
          ) : null}
          {status === "error" ? <p role="alert">{copy.error}</p> : null}
          {status === "ready" && items.length === 0 ? (
            <p role="status">{copy.empty}</p>
          ) : null}
          {status === "ready" && items.length > 0 ? (
            <ul id={listboxId} role="listbox">
              {items.map((item, index) => (
                <li
                  id={`${listboxId}-${index}`}
                  aria-selected={activeIndex === index}
                  className={activeIndex === index ? "is-active" : undefined}
                  key={item.symbol}
                  role="option"
                  onMouseDown={(event) => {
                    event.preventDefault();
                    selectCompany(item);
                  }}
                  onMouseEnter={() => setActiveIndex(index)}
                >
                  <strong>{item.symbol}</strong>
                  <span>{item.name}</span>
                  <small>{item.exchange ?? "US"}</small>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
