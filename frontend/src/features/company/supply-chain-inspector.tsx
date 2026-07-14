import type { CompanyPageCopy } from "./copy";
import type {
  SupplyChainGraphEdge,
  SupplyChainGraphNode,
  SupplyChainSource,
} from "@/lib/research/types";

type InspectorSelection =
  | { type: "node"; value: SupplyChainGraphNode }
  | { type: "edge"; value: SupplyChainGraphEdge };

export function SupplyChainInspector({
  copy,
  directEdges,
  locale,
  nodes,
  onCenterCompany,
  onClose,
  selection,
  sources,
}: {
  copy: CompanyPageCopy["graph"];
  directEdges: SupplyChainGraphEdge[];
  locale: string;
  nodes: SupplyChainGraphNode[];
  onCenterCompany: (symbol: string) => void;
  onClose: () => void;
  selection: InspectorSelection;
  sources: SupplyChainSource[];
}) {
  const sourceById = new Map(sources.map((source) => [source.id, source]));

  return (
    <aside className="supply-chain-inspector" aria-live="polite">
      <header>
        <h2>{selection.type === "node" ? copy.nodeDetails : copy.relationshipDetails}</h2>
        <button aria-label={copy.close} onClick={onClose} type="button">×</button>
      </header>
      {selection.type === "node" ? (
        <NodeEvidence
          copy={copy}
          directEdges={directEdges}
          node={selection.value}
          nodes={nodes}
          onCenterCompany={onCenterCompany}
        />
      ) : (
        <EdgeEvidence
          copy={copy}
          edge={selection.value}
          locale={locale}
          nodes={nodes}
          sourceById={sourceById}
        />
      )}
    </aside>
  );
}

function NodeEvidence({
  copy,
  directEdges,
  node,
  nodes,
  onCenterCompany,
}: {
  copy: CompanyPageCopy["graph"];
  directEdges: SupplyChainGraphEdge[];
  node: SupplyChainGraphNode;
  nodes: SupplyChainGraphNode[];
  onCenterCompany: (symbol: string) => void;
}) {
  return (
    <div className="supply-chain-inspector__body">
      <span className={`supply-chain-inspector__layer is-${node.layer}`}>
        {copy.layers[node.layer]} · {copy.kinds[node.kind]}
      </span>
      <h3>{node.label}</h3>
      <p>{node.description}</p>
      <dl>
        <div><dt>{copy.confidence}</dt><dd>{node.confidence}</dd></div>
        <div><dt>{copy.identity}</dt><dd>{node.symbol ?? "—"}{node.cik ? ` · CIK ${node.cik}` : ""}</dd></div>
      </dl>
      <h4>{copy.directRelationships}</h4>
      <ul className="supply-chain-inspector__relations">
        {directEdges.map((edge) => (
          <li key={edge.id}>{relationshipSentence(edge, nodes, copy)}</li>
        ))}
      </ul>
      {node.symbol ? (
        <button
          className="supply-chain-inspector__center"
          onClick={() => onCenterCompany(node.symbol!)}
          type="button"
        >
          {copy.centerCompany}
        </button>
      ) : null}
    </div>
  );
}

function EdgeEvidence({
  copy,
  edge,
  locale,
  nodes,
  sourceById,
}: {
  copy: CompanyPageCopy["graph"];
  edge: SupplyChainGraphEdge;
  locale: string;
  nodes: SupplyChainGraphNode[];
  sourceById: Map<string, SupplyChainSource>;
}) {
  return (
    <div className="supply-chain-inspector__body">
      <span className={`supply-chain-inspector__status is-${edge.evidence_status}`}>
        {edge.evidence_status === "verified" ? copy.verified : copy.potential}
      </span>
      <h3>{relationshipSentence(edge, nodes, copy)}</h3>
      <p>{edge.explanation}</p>
      <dl>
        <div><dt>{copy.confidence}</dt><dd>{edge.confidence}</dd></div>
        <div><dt>{copy.status}</dt><dd>{edge.evidence_status === "verified" ? copy.verified : copy.potential}</dd></div>
      </dl>
      <h4>{copy.sources}</h4>
      <div className="supply-chain-inspector__sources">
        {edge.citations.map((citation) => {
          const source = sourceById.get(citation.source_id);
          return (
            <article key={citation.id}>
              <header>
                <strong>{source?.title ?? citation.source_key}</strong>
                <span>{source?.publisher}{source?.published_at ? ` · ${formatDate(source.published_at, locale)}` : ""}</span>
              </header>
              <p>{copy.locator}: {citation.locator}</p>
              <blockquote>{citation.excerpt}</blockquote>
              {source ? (
                <a aria-label={copy.openSource} href={source.canonical_url} rel="noopener noreferrer" target="_blank">
                  {copy.openSource} ↗
                </a>
              ) : null}
            </article>
          );
        })}
      </div>
    </div>
  );
}

export function relationshipSentence(
  edge: SupplyChainGraphEdge,
  nodes: SupplyChainGraphNode[],
  copy: CompanyPageCopy["graph"],
) {
  const source = nodes.find((node) => node.id === edge.source)?.label ?? edge.source;
  const target = nodes.find((node) => node.id === edge.target)?.label ?? edge.target;
  const predicate = copy.predicates[edge.relationship_type as keyof typeof copy.predicates]
    ?? humanizePredicate(edge.relationship_type);
  return `${source} ${predicate.toLocaleLowerCase()} ${target}.`;
}

function humanizePredicate(value: string) {
  return value.replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());
}

function formatDate(value: string, locale: string) {
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: "UTC" }).format(new Date(value));
}
