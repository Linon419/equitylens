"use client";

import { useEffect, useRef, useState } from "react";

import type { ChatLocale, ChatMessage } from "@/lib/chat/types";
import type { CompanyChatCopy } from "../copy";
import { AnswerSections } from "./answer-sections";
import { ContextChips } from "./context-chips";
import { ConversationHistory } from "./conversation-history";
import { useCompanyChat } from "./use-company-chat";

export function ChatWorkbench({
  authenticated,
  copy,
  locale,
  onClose,
  open,
  symbol,
}: {
  authenticated: boolean;
  copy: CompanyChatCopy;
  locale: ChatLocale;
  onClose: () => void;
  open: boolean;
  symbol: string;
}) {
  const chat = useCompanyChat({ authenticated, locale, open, symbol });
  const [draft, setDraft] = useState("");
  const [historyOpen, setHistoryOpen] = useState(false);
  const messageEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (
      (chat.streaming || chat.messages.length > 0) &&
      typeof messageEnd.current?.scrollIntoView === "function"
    ) {
      messageEnd.current.scrollIntoView({ block: "end" });
    }
  }, [chat.live, chat.messages.length, chat.streaming]);

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
    <aside className="chat-workbench" aria-label={copy.title}>
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
          <button aria-label={copy.close} type="button" onClick={onClose}>×</button>
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
              <p className="chat-message__stage">{copy.stages[chat.live.stage]}</p>
            ) : (
              <p className="chat-message__stage">{copy.sending}</p>
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
