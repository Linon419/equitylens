import type { Citation, IntelligenceClaim } from "@/lib/research/types";
import type { SelectedChatContext } from "@/lib/chat/types";

export function BusinessSummary({
  citations,
  claims,
  copy,
  onAskContext,
  onCitation,
  snapshotId,
}: {
  citations: Citation[];
  claims: IntelligenceClaim[];
  copy: {
    eyebrow: string;
    title: string;
    ask: string;
    empty: string;
    revenue: string;
    citation: string;
  };
  onAskContext?: (context: SelectedChatContext) => void;
  onCitation: (citation: Citation) => void;
  snapshotId?: string;
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
                {onAskContext && snapshotId ? (
                  <button
                    aria-label={`${copy.ask}: ${claim.title}`}
                    className="business-summary__ask"
                    type="button"
                    onClick={() => onAskContext({
                      key: `business_claim:${claim.claim_id}:${snapshotId}`,
                      label: claim.title,
                      selection: {
                        kind: "business_claim",
                        id: claim.claim_id,
                        snapshot_id: snapshotId,
                      },
                    })}
                  >
                    {copy.ask} ↗
                  </button>
                ) : null}
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
