import type {
  ChatCitation,
  ChatSections,
  EvidenceCoverage,
} from "@/lib/chat/types";
import type { CompanyChatCopy } from "../copy";

const EMPTY_SECTIONS: ChatSections = {
  direct_conclusion: "",
  key_evidence: "",
  risks_and_uncertainties: "",
  sources: "",
};

export function AnswerSections({
  citations,
  content,
  copy,
  coverage,
  sections,
}: {
  citations: ChatCitation[];
  content?: string;
  copy: CompanyChatCopy;
  coverage?: EvidenceCoverage | null;
  sections?: ChatSections;
}) {
  const resolved = sections ?? parseStoredAnswer(content ?? "");
  const entries = [
    ["direct_conclusion", copy.sections.directConclusion],
    ["key_evidence", copy.sections.keyEvidence],
    ["risks_and_uncertainties", copy.sections.risksAndUncertainties],
    ["sources", copy.sections.sources],
  ] as const;

  return (
    <div className="chat-answer">
      {coverage ? (
        <p className={`chat-answer__coverage chat-answer__coverage--${coverage}`}>
          {copy.evidenceCoverage}: {coverage}
        </p>
      ) : null}
      {entries.map(([key, label]) =>
        resolved[key] ? (
          <section className={`chat-answer__section chat-answer__section--${key}`} key={key}>
            <h3>{label}</h3>
            <PlainResearchText text={resolved[key]} />
          </section>
        ) : null,
      )}
      {citations.length > 0 ? (
        <section className="chat-citations" aria-label={copy.sources}>
          <h3>{copy.sources}</h3>
          <ol>
            {citations.map((citation) => (
              <li key={citation.id}>
                <a
                  href={citation.source_url}
                  rel="noopener noreferrer"
                  target="_blank"
                >
                  <span>[{citation.ordinal + 1}]</span> {citation.title} ↗
                </a>
                <dl>
                  <div><dt>{copy.sourceTier}</dt><dd>{citation.source_tier}</dd></div>
                  {citation.published_at ? (
                    <div><dt>{copy.published}</dt><dd>{date(citation.published_at)}</dd></div>
                  ) : null}
                  <div><dt>{copy.retrieved}</dt><dd>{date(citation.retrieved_at)}</dd></div>
                  {citation.source_anchor ? (
                    <div><dt>{copy.sourceLocation}</dt><dd>{citation.source_anchor}</dd></div>
                  ) : null}
                </dl>
                <blockquote>
                  <span>{copy.excerpt}</span>
                  {citation.excerpt}
                </blockquote>
              </li>
            ))}
          </ol>
        </section>
      ) : null}
    </div>
  );
}

function PlainResearchText({ text }: { text: string }) {
  const lines = text.split("\n").filter((line) => line.trim());
  const list = lines.every((line) => line.startsWith("- "));
  if (list) {
    return <ul>{lines.map((line, index) => <li key={index}>{line.slice(2)}</li>)}</ul>;
  }
  return <>{lines.map((line, index) => <p key={index}>{line.replace(/^- /, "")}</p>)}</>;
}

function parseStoredAnswer(content: string): ChatSections {
  const sections = { ...EMPTY_SECTIONS };
  const headings: Record<string, keyof ChatSections> = {
    conclusion: "direct_conclusion",
    "direct conclusion": "direct_conclusion",
    "key evidence": "key_evidence",
    "risks and uncertainties": "risks_and_uncertainties",
    sources: "sources",
    结论: "direct_conclusion",
    直接结论: "direct_conclusion",
    关键证据: "key_evidence",
    风险与不确定性: "risks_and_uncertainties",
    来源: "sources",
  };
  let current: keyof ChatSections = "direct_conclusion";
  for (const line of content.split("\n")) {
    const heading = line.match(/^##\s+(.+)$/)?.[1]?.trim().toLowerCase();
    if (heading && headings[heading]) {
      current = headings[heading];
      continue;
    }
    if (line.trim()) sections[current] += `${sections[current] ? "\n" : ""}${line}`;
  }
  return sections;
}

function date(value: string): string {
  return value.slice(0, 10);
}
