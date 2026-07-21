import type { MarketMetric, MarketResponse } from "@/lib/research/types";
import type { SelectedChatContext } from "@/lib/chat/types";

type MarketCopy = {
  eyebrow: string;
  title: string;
  ask: string;
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
  onAskContext,
}: {
  copy: MarketCopy;
  data: MarketResponse;
  locale: "en-US" | "zh-CN";
  onAskContext?: (context: SelectedChatContext) => void;
}) {
  const cards: Array<[
    "price" | "market_cap" | "trailing_eps" | "trailing_pe" | "forward_pe",
    string,
    MarketMetric,
    "money" | "compact" | "multiple",
  ]> = [
    ["price", copy.price, data.price, "money"],
    ["market_cap", copy.marketCap, data.market_cap, "compact"],
    ["trailing_eps", copy.trailingEps, data.trailing_eps, "money"],
    ["trailing_pe", copy.trailingPe, data.trailing_pe, "multiple"],
    ["forward_pe", copy.forwardPe, data.forward_pe, "multiple"],
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
          <small>{copy.provider}: {data.provider}</small>
        </div>
      </header>
      <div className="market-cards">
        {cards.map(([key, label, metric, format]) => (
          <article key={key}>
            <span>{label}</span>
            <strong>{formatMetric(metric, format, locale)}</strong>
            {metric.missing_reason ? <small>{metric.missing_reason}</small> : null}
            {onAskContext ? (
              <button
                aria-label={`${copy.ask}: ${label}`}
                type="button"
                onClick={() => onAskContext({
                  key: `market_metric:${key}`,
                  label,
                  selection: {
                    kind: "market_metric",
                    metric_key: key,
                    observed_at: data.observed_at,
                  },
                })}
              >
                {copy.ask} ↗
              </button>
            ) : null}
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
