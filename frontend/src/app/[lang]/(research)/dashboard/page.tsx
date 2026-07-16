import { notFound } from "next/navigation";

import { getDictionary } from "@/dictionaries";
import { CompanySearch } from "@/features/research/company-search";
import { Watchlist } from "@/features/research/watchlist";
import { isLocale } from "@/lib/i18n";

export default async function Dashboard({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!isLocale(lang)) notFound();
  const copy = getDictionary(lang).app.dashboard;

  return (
    <div className="research-dashboard">
      <section className="research-dashboard__hero">
        <div className="research-dashboard__lead reveal reveal--one">
          <p className="research-dashboard__eyebrow">{copy.eyebrow}</p>
          <h1>{copy.title}</h1>
          <p className="research-dashboard__description">{copy.description}</p>
          <p className="research-dashboard__coverage">{copy.coverage}</p>
        </div>
        <div className="research-dashboard__search reveal reveal--two">
          <span className="research-dashboard__folio">Company index / 001</span>
          <CompanySearch copy={copy.search} locale={lang} />
          <div className="research-dashboard__search-meta" aria-hidden="true">
            <span><small>01</small>10-K / 10-Q</span>
            <span><small>02</small>VALUE CHAIN</span>
            <span><small>03</small>MARKET + VALUE</span>
          </div>
        </div>
      </section>

      <section className="research-workflow">
        <header>
          <p>{copy.workflow.eyebrow}</p>
          <h2>{copy.workflow.title}</h2>
        </header>
        <ol>
          {copy.workflow.items.map((item) => (
            <li key={item.number}>
              <span>{item.number}</span>
              <h3>{item.title}</h3>
              <p>{item.description}</p>
            </li>
          ))}
        </ol>
      </section>

      <div className="research-dashboard__watchlist">
        <Watchlist copy={copy.watchlist} locale={lang} />
      </div>
    </div>
  );
}
