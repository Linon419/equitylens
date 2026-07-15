"use client";

import { useEffect, useRef, useState } from "react";

import type {
  ChatLocale,
  ChatMessage,
  SelectedChatContext,
} from "@/lib/chat/types";
import type { CompanyChatCopy } from "../copy";
import { AnswerSections } from "./answer-sections";
import { ContextChips } from "./context-chips";
import { ConversationHistory } from "./conversation-history";
import { ReadinessPanel } from "./readiness-panel";
import { useCompanyChat } from "./use-company-chat";

export function ChatWorkbench({
  authenticated,
  copy,
  locale,
  onClose,
  onContextConsumed,
  onReadinessNavigate,
  open,
  pendingContext,
  symbol,
}: {
  authenticated: boolean;
  copy: CompanyChatCopy;
  locale: ChatLocale;
  onClose: () => void;
  onContextConsumed?: () => void;
  onReadinessNavigate?: (action: "company_analysis" | "supply_chain_graph") => void;
  open: boolean;
  pendingContext?: SelectedChatContext | null;
  symbol: string;
}) {
  const chat = useCompanyChat({ authenticated, locale, open, symbol });
  const addContext = chat.addContext;
  const [draft, setDraft] = useState("");
  const [historyOpen, setHistoryOpen] = useState(false);
  const messageEnd = useRef<HTMLDivElement>(null);
  const panel = useRef<HTMLElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (
      (chat.streaming || chat.messages.length > 0) &&
      typeof messageEnd.current?.scrollIntoView === "function"
    ) {
      messageEnd.current.scrollIntoView({ block: "end" });
    }
  }, [chat.live, chat.messages.length, chat.streaming]);

  useEffect(() => {
    if (!open || !pendingContext) return;
    addContext(pendingContext);
    onContextConsumed?.();
  }, [addContext, onContextConsumed, open, pendingContext]);

  useEffect(() => {
    if (!open) return;
    const origin = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    const focusTimer = window.setTimeout(() => closeButton.current?.focus(), 0);
    const trapFocus = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeButton.current?.click();
        return;
      }
      if (event.key !== "Tab" || !panel.current) return;
      const controls = focusableElements(panel.current);
      const first = controls[0];
      const last = controls.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", trapFocus);
    return () => {
      window.clearTimeout(focusTimer);
      document.removeEventListener("keydown", trapFocus);
      window.setTimeout(() => origin?.focus(), 0);
    };
  }, [open]);

  if (!open) return null;
  const quotaEmpty = chat.quota?.remaining === 0;
  const composerDisabled =
    chat.loading || chat.streaming || !chat.selectedConversation || quotaEmpty;

  function submit() {
    const question = draft.trim();
    if (!question || composerDisabled) return;
    setDraft("");
    void chat.send(question);
  }

  return (
    <>
    <button
      aria-hidden="true"
      className="chat-workbench__backdrop"
      tabIndex={-1}
      type="button"
      onClick={onClose}
    />
    <aside
      aria-label={copy.title}
      aria-modal="true"
      className="chat-workbench"
      ref={panel}
      role="dialog"
    >
      <header className="chat-workbench__header">
        <div>
          <p>{copy.eyebrow}</p>
          <div className="chat-workbench__identity">
            <span>{symbol}</span>
            <h2>{chat.selectedConversation?.title ?? copy.title}</h2>
          </div>
        </div>
        <div className="chat-workbench__tools">
          <button
            aria-expanded={historyOpen}
            type="button"
            onClick={() => setHistoryOpen((current) => !current)}
          >
            {historyOpen ? copy.hideHistory : copy.history}
          </button>
          <button
            aria-label={copy.close}
            ref={closeButton}
            type="button"
            onClick={onClose}
          >×</button>
        </div>
      </header>

      {historyOpen ? (
        <ConversationHistory
          authenticated={authenticated}
          conversations={chat.conversations}
          copy={copy}
          onArchive={(id) => void chat.archiveConversation(id)}
          onNew={() => void chat.createConversation()}
          onRename={(id, title) => void chat.renameConversation(id, title)}
          onSelect={(id) => {
            setHistoryOpen(false);
            void chat.selectConversation(id);
          }}
          onStartFresh={() => void chat.startFresh()}
          selectedId={chat.selectedId}
        />
      ) : null}

      <div className="chat-workbench__messages">
        {chat.readiness ? (
          <ReadinessPanel
            copy={copy}
            onNavigate={(action) => onReadinessNavigate?.(action)}
            onRefresh={() => void chat.refreshReadiness()}
            readiness={chat.readiness}
            symbol={symbol}
          />
        ) : null}
        {chat.loading && chat.messages.length === 0 ? (
          <p className="chat-workbench__empty">{copy.sending}</p>
        ) : null}
        {chat.nextCursor ? (
          <button className="chat-workbench__more" type="button" onClick={() => void chat.loadMore()}>
            {copy.loadMore}
          </button>
        ) : null}
        {chat.messages.length === 0 && !chat.loading ? (
          <EmptyPrompt copy={copy} onSelect={setDraft} />
        ) : null}
        {chat.messages.map((message) => (
          <MessageBubble
            copy={copy}
            key={message.id}
            message={message}
            onRetry={() => void chat.retry(message.id)}
          />
        ))}
        {chat.live ? (
          <article className="chat-message chat-message--assistant chat-message--live">
            {chat.live.stage ? (
              <p aria-live="polite" className="chat-message__stage">
                {copy.stages[chat.live.stage]}
              </p>
            ) : (
              <p aria-live="polite" className="chat-message__stage">{copy.sending}</p>
            )}
            <AnswerSections
              citations={chat.live.citations}
              copy={copy}
              sections={chat.live.sections}
            />
          </article>
        ) : null}
        {chat.error && !chat.error.retryable ? (
          <p className="chat-workbench__error" role="alert">
            {errorCopy(chat.error.code, copy)}
          </p>
        ) : null}
        <div ref={messageEnd} />
      </div>

      <footer className="chat-composer">
        <ContextChips
          copy={copy}
          items={chat.contexts}
          onClear={chat.clearContexts}
          onRemove={chat.removeContext}
        />
        <p className="chat-composer__web"><span>WEB / AUTO</span>{copy.webAutomatic}</p>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          <label htmlFor="company-chat-question">{copy.question}</label>
          <textarea
            aria-label={copy.question}
            disabled={composerDisabled}
            id="company-chat-question"
            maxLength={2_000}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={copy.placeholder}
            rows={3}
            value={draft}
          />
          <button
            aria-label={copy.send}
            disabled={composerDisabled || !draft.trim()}
            type="submit"
          >
            {chat.streaming ? copy.sending : copy.send} <span>↗</span>
          </button>
        </form>
        <QuotaLine copy={copy} quota={chat.quota} />
        <p className="chat-composer__disclaimer">{copy.disclaimer}</p>
      </footer>
    </aside>
    </>
  );
}

function MessageBubble({
  copy,
  message,
  onRetry,
}: {
  copy: CompanyChatCopy;
  message: ChatMessage;
  onRetry: () => void;
}) {
  if (message.role === "user") {
    return <article className="chat-message chat-message--user"><p>{message.content}</p></article>;
  }
  if (message.state === "failed") {
    return (
      <article className="chat-message chat-message--assistant chat-message--failed">
        <p>{errorCopy(message.error_code, copy)}</p>
        <button type="button" onClick={onRetry}>{copy.retry}</button>
      </article>
    );
  }
  if (
    message.response_kind === "conversation" ||
    message.response_kind === "clarification"
  ) {
    return (
      <article className="chat-message chat-message--assistant chat-message--plain">
        <p>{message.content}</p>
      </article>
    );
  }
  return (
    <article className="chat-message chat-message--assistant">
      <AnswerSections
        citations={message.citations}
        content={message.content}
        copy={copy}
        coverage={message.evidence_coverage}
      />
    </article>
  );
}

function EmptyPrompt({
  copy,
  onSelect,
}: {
  copy: CompanyChatCopy;
  onSelect: (question: string) => void;
}) {
  return (
    <section className="chat-workbench__empty">
      <p>{copy.empty}</p>
      <span>{copy.suggestedLabel}</span>
      <div>
        {copy.suggestedQuestions.map((question, index) => (
          <button key={question} type="button" onClick={() => onSelect(question)}>
            <small>0{index + 1}</small>{question}
          </button>
        ))}
      </div>
    </section>
  );
}

function QuotaLine({
  copy,
  quota,
}: {
  copy: CompanyChatCopy;
  quota: ReturnType<typeof useCompanyChat>["quota"];
}) {
  if (!quota) return <p className="chat-composer__quota">{copy.quotaUnavailable}</p>;
  if (quota.remaining === 0) return <p className="chat-composer__quota is-empty">{copy.quotaUsed}</p>;
  const unit = quota.remaining === 1 ? copy.quotaRemaining : copy.quotaRemainingPlural;
  return (
    <p className="chat-composer__quota">
      <span className="chat-composer__quota-count">{quota.remaining} {unit}</span>
      <span>{copy.quotaReset} {quota.resets_at.slice(0, 10)}</span>
    </p>
  );
}

function errorCopy(code: string | null, copy: CompanyChatCopy): string {
  if (code?.includes("QUOTA")) return copy.errors.quota;
  if (code === "CHAT_LOAD_FAILED") return copy.errors.load;
  if (code === "CHAT_STREAM_INTERRUPTED") return copy.errors.stream;
  return copy.errors.generic;
}

function focusableElements(container: HTMLElement): HTMLElement[] {
  return [...container.querySelectorAll<HTMLElement>(
    'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
  )].filter((element) => !element.hasAttribute("hidden"));
}
