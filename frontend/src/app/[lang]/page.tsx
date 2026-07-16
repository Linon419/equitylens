import { notFound } from "next/navigation";

import { BrandMark } from "@/components/brand-mark";
import { LanguageSwitcher } from "@/components/language-switcher";
import { getDictionary } from "@/dictionaries";
import { isLocale } from "@/lib/i18n";

type HomeProps = {
  params: Promise<{ lang: string }>;
};

export default async function Home({ params }: HomeProps) {
  const { lang } = await params;
  if (!isLocale(lang)) {
    notFound();
  }
  const copy = getDictionary(lang);

  return (
    <main className="site-shell">
      <div className="ambient-grid" aria-hidden="true" />
      <header className="masthead">
        <a className="wordmark" href={`/${lang}`}>
          <BrandMark />
          <span>EquityLens</span>
        </a>
        <nav aria-label="Primary navigation" className="desktop-nav">
          {copy.nav.map((item, index) => (
            <a href="#research-frame" key={item}>
              <span>0{index + 1}</span>
              {item}
            </a>
          ))}
        </nav>
        <LanguageSwitcher locale={lang} label={copy.language} />
      </header>

      <section className="hero">
        <div className="hero__copy">
          <p className="eyebrow reveal reveal--one">{copy.hero.eyebrow}</p>
          <p className="product-name reveal reveal--one">{copy.brand}</p>
          <h1 className="reveal reveal--two">{copy.hero.title}</h1>
          <p className="hero__description reveal reveal--three">
            {copy.hero.description}
          </p>
          <div className="hero__actions reveal reveal--four">
            <a className="button button--primary" href={`/${lang}/login`}>
              {copy.hero.primaryAction}
              <span aria-hidden="true">↗</span>
            </a>
            <a className="button button--secondary" href="#document-center">
              {copy.hero.secondaryAction}
            </a>
          </div>
          <p className="coverage reveal reveal--four">{copy.coverage}</p>
        </div>

        <ResearchFrame copy={copy.frame} />
      </section>

      <section className="evidence" id="document-center">
        <div className="evidence__lead">
          <p className="eyebrow">{copy.evidence.label}</p>
          <h2>{copy.evidence.title}</h2>
        </div>
        <p className="evidence__description">{copy.evidence.description}</p>
        <dl className="evidence__facts">
          <div>
            <dt>{copy.evidence.source}</dt>
            <dd>{copy.evidence.sourceValue}</dd>
          </div>
          <div>
            <dt>{copy.evidence.language}</dt>
            <dd>{copy.evidence.languageValue}</dd>
          </div>
        </dl>
      </section>
    </main>
  );
}

type ResearchFrameProps = {
  copy: ReturnType<typeof getDictionary>["frame"];
};

function ResearchFrame({ copy }: ResearchFrameProps) {
  return (
    <aside className="research-frame reveal reveal--three" id="research-frame">
      <div className="research-frame__header">
        <p>{copy.kicker}</p>
        <span className="live-dot">{copy.status}</span>
      </div>
      <h2>{copy.title}</h2>
      <div className="research-frame__ticker" aria-hidden="true">
        <div>
          <span>TICKER</span>
          <strong>— — —</strong>
        </div>
        <span className="ticker-arrow">↘</span>
      </div>
      <ol className="research-frame__list">
        {copy.items.map(([title, description], index) => (
          <li key={title}>
            <span className="item-number">0{index + 1}</span>
            <div>
              <h3>{title}</h3>
              <p>{description}</p>
            </div>
            <span aria-hidden="true" className="item-arrow">
              ↗
            </span>
          </li>
        ))}
      </ol>
    </aside>
  );
}
