import { notFound } from "next/navigation";

import { LanguageSwitcher } from "@/components/language-switcher";
import { getDictionary } from "@/dictionaries";
import { isLocale } from "@/lib/i18n";

export default async function Settings({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!isLocale(lang)) {
    notFound();
  }
  const copy = getDictionary(lang);

  return (
    <section className="settings-card">
      <p className="eyebrow">{copy.app.settings.eyebrow}</p>
      <h1>{copy.app.settings.title}</h1>
      <div className="settings-card__field">
        <span>{copy.app.settings.language}</span>
        <LanguageSwitcher
          authenticated
          locale={lang}
          label={copy.app.settings.language}
        />
      </div>
    </section>
  );
}
