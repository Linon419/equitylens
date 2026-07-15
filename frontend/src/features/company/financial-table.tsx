import type { FinancialsResponse } from "@/lib/research/types";
import type { SelectedChatContext } from "@/lib/chat/types";

const METRICS = [
  "revenue",
  "net_income",
  "operating_cash_flow",
  "capital_expenditure",
  "free_cash_flow",
] as const;

const LABELS = {
  en: {
    metric: "Metric",
    revenue: "Revenue",
    net_income: "Net income",
    operating_cash_flow: "Operating cash flow",
    capital_expenditure: "Capital expenditure",
    free_cash_flow: "Free cash flow",
  },
  zh: {
    metric: "指标",
    revenue: "营业收入",
    net_income: "净利润",
    operating_cash_flow: "经营现金流",
    capital_expenditure: "资本开支",
    free_cash_flow: "自由现金流",
  },
} as const;

export function FinancialTable({
  askLabel,
  data,
  locale,
  onAskContext,
}: {
  askLabel?: string;
  data: FinancialsResponse;
  locale: "en" | "zh";
  onAskContext?: (context: SelectedChatContext) => void;
}) {
  const labels = LABELS[locale];
  const periods = Array.from(
    new Set(
      data.series.flatMap((series) =>
        series.annual.map((point) => point.period_key),
      ),
    ),
  ).sort((left, right) => left.localeCompare(right));

  return (
    <div className="financial-table-wrap">
      <p className="financial-table__unit">USD · {data.source}</p>
      <table className="financial-table">
        <thead>
          <tr>
            <th scope="col">{labels.metric}</th>
            {periods.map((period) => (
              <th key={period} scope="col">{formatPeriod(period, locale)}</th>
            ))}
            <th scope="col">TTM</th>
          </tr>
        </thead>
        <tbody>
          {METRICS.map((metric) => {
            const series = data.series.find((item) => item.metric_key === metric);
            return (
              <tr key={metric}>
                <th scope="row">{labels[metric]}</th>
                {periods.map((period) => (
                  <td key={period}>
                    <FinancialValue
                      askLabel={askLabel}
                      label={labels[metric]}
                      locale={locale}
                      metric={metric}
                      onAskContext={onAskContext}
                      period={period}
                      value={series?.annual.find((point) => point.period_key === period)?.value}
                    />
                  </td>
                ))}
                <td>
                  <FinancialValue
                    askLabel={askLabel}
                    label={labels[metric]}
                    locale={locale}
                    metric={metric}
                    onAskContext={onAskContext}
                    period="TTM"
                    value={series?.ttm?.value}
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function FinancialValue({
  askLabel,
  label,
  locale,
  metric,
  onAskContext,
  period,
  value,
}: {
  askLabel?: string;
  label: string;
  locale: "en" | "zh";
  metric: string;
  onAskContext?: (context: SelectedChatContext) => void;
  period: string;
  value?: string;
}) {
  const periodLabel = period === "TTM" ? period : formatPeriod(period, locale);
  if (!onAskContext || !askLabel) return formatFinancial(value, locale);
  return (
    <button
      aria-label={`${askLabel}: ${label} ${periodLabel}`}
      className="financial-table__ask"
      type="button"
      onClick={() => onAskContext({
        key: `financial_metric:${metric}:${period}`,
        label: `${label} · ${periodLabel}`,
        selection: {
          kind: "financial_metric",
          metric_key: metric,
          period_key: period,
        },
      })}
    >
      {formatFinancial(value, locale)} <span aria-hidden="true">↗</span>
    </button>
  );
}

function formatPeriod(period: string, locale: "en" | "zh") {
  const year = period.replace(/^FY/, "");
  return locale === "en" ? `FY ${year}` : `${year} 财年`;
}

function formatFinancial(value: string | undefined, locale: "en" | "zh") {
  if (value === undefined) return "—";
  const number = Number(value);
  const formatted = new Intl.NumberFormat(locale === "en" ? "en-US" : "zh-CN", {
    style: "currency",
    currency: "USD",
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(Math.abs(number));
  return number < 0 ? `−${formatted}` : formatted;
}
