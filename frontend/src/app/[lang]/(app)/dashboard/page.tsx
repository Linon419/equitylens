import { notFound } from "next/navigation";

import { getDictionary } from "@/dictionaries";
import { isLocale } from "@/lib/i18n";

export default async function Dashboard({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!isLocale(lang)) {
    notFound();
  }
  const copy = getDictionary(lang).app.dashboard;

  return (
    <section className="workspace-empty">
      <p className="eyebrow">{copy.eyebrow}</p>
      <h1>{copy.title}</h1>
      <p>{copy.description}</p>
    </section>
  );
}
