import type { MarketMetric, MarketResponse } from "@/lib/research/types";

type MarketCopy = {
  eyebrow: string;
  title: string;
  price: string;
  marketCap: string;
  trailingEps: string;
  trailingPe: string;
  forwardPe: string;
  stale: string;
  observed: string;
  provider: string;
};

export function MarketContext({
  copy,
  data,
  locale,
}: {
  copy: MarketCopy;
  data: MarketResponse;
  locale: "en-US" | "zh-CN";
}) {
  const cards: Array<[string, MarketMetric, "money" | "compact" | "multiple"]> = [
    [copy.price, data.price, "money"],
    [copy.marketCap, data.market_cap, "compact"],
    [copy.trailingEps, data.trailing_eps, "money"],
    [copy.trailingPe, data.trailing_pe, "multiple"],
    [copy.forwardPe, data.forward_pe, "multiple"],
  ];
  return (
    <section className="company-section company-market">
      <header className="company-section__header">
        <div>
          <p>{copy.eyebrow}</p>
          <h2>{copy.title}</h2>
        </div>
        <div className="company-market__time">
          {data.freshness === "stale" ? <strong>{copy.stale}</strong> : null}
          <span>{copy.observed}: {formatDateTime(data.observed_at, locale)}</span>
          <small>{copy.provider}</small>
        </div>
      </header>
      <div className="market-cards">
        {cards.map(([label, metric, format]) => (
          <article key={label}>
            <span>{label}</span>
            <strong>{formatMetric(metric, format, locale)}</strong>
            {metric.missing_reason ? <small>{metric.missing_reason}</small> : null}
          </article>
        ))}
      </div>
    </section>
  );
}

function formatMetric(
  metric: MarketMetric,
  format: "money" | "compact" | "multiple",
  locale: "en-US" | "zh-CN",
) {
  if (metric.value === null) return "N/M";
  const value = Number(metric.value);
  if (format === "multiple") return `${value.toFixed(1)}×`;
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency: "USD",
    notation: format === "compact" ? "compact" : "standard",
    maximumFractionDigits: format === "compact" ? 1 : 2,
  }).format(value);
}

function formatDateTime(value: string, locale: "en-US" | "zh-CN") {
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(value));
}
