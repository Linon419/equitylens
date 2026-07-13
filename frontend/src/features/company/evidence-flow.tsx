"use client";

import { useState } from "react";

import { companyPageCopy } from "./copy";
import { CitationPanel } from "./citation-panel";
import type {
  Citation,
  IntelligenceClaim,
  IntelligenceResponse,
} from "@/lib/research/types";

export function EvidenceFlow({
  intelligence,
  locale,
}: {
  intelligence: IntelligenceResponse;
  locale: "en" | "zh";
}) {
  const copy = companyPageCopy[locale].evidence;
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const lanes: Array<[string, IntelligenceClaim[]]> = [
    [copy.upstream, intelligence.content.upstream],
    [copy.company, intelligence.content.company_layer],
    [copy.downstream, intelligence.content.downstream],
  ];

  return (
    <section className="company-section evidence-flow">
      <header className="company-section__header">
        <div><p>{copy.eyebrow}</p><h2>{copy.title}</h2></div>
        <a href={intelligence.filing_url} rel="noopener noreferrer" target="_blank">
          {copy.viewFiling} <span aria-hidden="true">↗</span>
        </a>
      </header>
      {intelligence.evidence_coverage === "partial" ? (
        <p className="evidence-flow__notice">{copy.partial}</p>
      ) : null}
      {intelligence.evidence_coverage === "insufficient_evidence" ? (
        <p className="evidence-flow__notice evidence-flow__notice--warning">
          {copy.insufficient}
        </p>
      ) : null}
      <div className="evidence-flow__lanes">
        {lanes.map(([title, claims], laneIndex) => (
          <div className="evidence-flow__lane" key={title}>
            <header>
              <span>0{laneIndex + 1}</span>
              <h3>{title}</h3>
            </header>
            <div className="evidence-flow__claims">
              {claims.map((claim) => (
                <article
                  className={claim.confidence === "Low" ? "is-low-confidence" : undefined}
                  key={claim.claim_id}
                >
                  <h4>{claim.title}</h4>
                  <p>{claim.explanation}</p>
                  {claim.confidence === "Low" ? <small>{copy.low}</small> : null}
                  <div className="claim-citations">
                    {claim.citation_ids.map((citationId) => {
                      const citation = intelligence.citations.find(
                        (item) => item.id === citationId,
                      );
                      return citation ? (
                        <button
                          key={citationId}
                          type="button"
                          onClick={() => setSelectedCitation(citation)}
                        >
                          {copy.citation} {citationId.replace("citation-", "")}
                        </button>
                      ) : null;
                    })}
                  </div>
                </article>
              ))}
            </div>
            {laneIndex < lanes.length - 1 ? (
              <svg aria-hidden="true" viewBox="0 0 48 16">
                <path d="M1 8h42m-6-6 6 6-6 6" />
              </svg>
            ) : null}
          </div>
        ))}
      </div>
      {selectedCitation ? (
        <CitationPanel
          citation={selectedCitation}
          copy={{
            title: copy.sourceDialog,
            open: copy.openFiling,
            close: copy.close,
          }}
          onClose={() => setSelectedCitation(null)}
        />
      ) : null}
    </section>
  );
}
