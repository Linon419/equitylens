"use client";

import { useEffect } from "react";

import type { Citation } from "@/lib/research/types";

export function CitationPanel({
  citation,
  copy,
  onClose,
}: {
  citation: Citation;
  copy: {
    title: string;
    open: string;
    close: string;
  };
  onClose: () => void;
}) {
  useEffect(() => {
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  return (
    <div
      aria-labelledby="citation-panel-title"
      aria-modal="true"
      className="citation-panel"
      role="dialog"
    >
      <button
        aria-label={copy.close}
        className="citation-panel__backdrop"
        type="button"
        onClick={onClose}
      />
      <article>
        <header>
          <div>
            <p>Form {citation.filing_type} · {citation.filing_date}</p>
            <h2 id="citation-panel-title">{copy.title}</h2>
          </div>
          <button aria-label={copy.close} type="button" onClick={onClose}>
            ×
          </button>
        </header>
        <p className="citation-panel__section">{citation.section}</p>
        <blockquote>{citation.excerpt.slice(0, 600)}</blockquote>
        <a
          href={citation.source_url}
          rel="noopener noreferrer"
          target="_blank"
        >
          {copy.open} <span aria-hidden="true">↗</span>
        </a>
      </article>
    </div>
  );
}
