import type { CompanyPageCopy } from "./copy";

export function SupplyChainLegend({ copy }: { copy: CompanyPageCopy["graph"] }) {
  return (
    <div className="supply-chain-legend" aria-label="Supply-chain graph legend">
      {(Object.keys(copy.layers) as Array<keyof typeof copy.layers>).map((layer) => (
        <span key={layer}><i className={`is-${layer}`} />{copy.layers[layer]}</span>
      ))}
      <span><i className="is-verified" />{copy.verified}</span>
      <span><i className="is-potential" />{copy.potentialToggle}</span>
    </div>
  );
}
