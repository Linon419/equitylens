import type { Citation, IntelligenceClaim } from "@/lib/research/types";

export function BusinessSummary({
  citations,
  claims,
  copy,
  onCitation,
}: {
  citations: Citation[];
  claims: IntelligenceClaim[];
  copy: {
    eyebrow: string;
    title: string;
    empty: string;
    revenue: string;
    citation: string;
  };
  onCitation: (citation: Citation) => void;
}) {
  return (
    <section className="company-section business-summary">
      <header className="company-section__header">
        <div><p>{copy.eyebrow}</p><h2>{copy.title}</h2></div>
      </header>
      {claims.length === 0 ? <p>{copy.empty}</p> : (
        <ol>
          {claims.map((claim, index) => (
            <li key={claim.claim_id}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <div>
                <h3>{claim.title}</h3>
                <p>{claim.explanation}</p>
                {claim.revenue_share ? (
                  <strong>{copy.revenue}: {claim.revenue_share}% · {claim.revenue_period}</strong>
                ) : null}
                <div className="claim-citations">
                  {claim.citation_ids.map((citationId) => {
                    const citation = citations.find((item) => item.id === citationId);
                    return citation ? (
                      <button key={citationId} type="button" onClick={() => onCitation(citation)}>
                        {copy.citation} {citationId.replace("citation-", "")}
                      </button>
                    ) : null;
                  })}
                </div>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
