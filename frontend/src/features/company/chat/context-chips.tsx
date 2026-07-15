import type { SelectedChatContext } from "@/lib/chat/types";
import type { CompanyChatCopy } from "../copy";

export function ContextChips({
  copy,
  items,
  onClear,
  onRemove,
}: {
  copy: CompanyChatCopy;
  items: SelectedChatContext[];
  onClear: () => void;
  onRemove: (key: string) => void;
}) {
  if (items.length === 0) return null;
  return (
    <section className="chat-context" aria-label={copy.selectedContext}>
      <header>
        <span>{copy.selectedContext}</span>
        <button type="button" onClick={onClear}>{copy.clearContext}</button>
      </header>
      <ul>
        {items.map((item) => (
          <li key={item.key}>
            <span>{item.label}</span>
            <button
              aria-label={`${copy.removeContext}: ${item.label}`}
              type="button"
              onClick={() => onRemove(item.key)}
            >
              ×
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
