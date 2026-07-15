"use client";

import { useState } from "react";

import type { ChatConversation } from "@/lib/chat/types";
import type { CompanyChatCopy } from "../copy";

export function ConversationHistory({
  authenticated,
  conversations,
  copy,
  onArchive,
  onNew,
  onRename,
  onSelect,
  onStartFresh,
  selectedId,
}: {
  authenticated: boolean;
  conversations: ChatConversation[];
  copy: CompanyChatCopy;
  onArchive: (id: string) => void;
  onNew: () => void;
  onRename: (id: string, title: string) => void;
  onSelect: (id: string) => void;
  onStartFresh: () => void;
  selectedId: string | null;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [title, setTitle] = useState("");

  function startRename(conversation: ChatConversation) {
    setEditingId(conversation.id);
    setTitle(conversation.title);
  }

  function saveRename() {
    if (editingId && title.trim()) onRename(editingId, title.trim());
    setEditingId(null);
  }

  return (
    <aside className="chat-history" aria-label={copy.history}>
      <header>
        <div>
          <p>{authenticated ? copy.userHistory : copy.guestHistory}</p>
          <strong>{copy.history}</strong>
        </div>
        {authenticated ? (
          <button aria-label={copy.newConversation} type="button" onClick={onNew}>
            + {copy.newConversation}
          </button>
        ) : null}
      </header>
      <ol>
        {conversations.map((conversation) => (
          <li
            className={conversation.id === selectedId ? "is-selected" : undefined}
            key={conversation.id}
          >
            {editingId === conversation.id ? (
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  saveRename();
                }}
              >
                <label>
                  <span>{copy.conversationTitle}</span>
                  <input
                    aria-label={copy.conversationTitle}
                    maxLength={120}
                    onChange={(event) => setTitle(event.target.value)}
                    value={title}
                  />
                </label>
                <div>
                  <button type="submit">{copy.saveTitle}</button>
                  <button type="button" onClick={() => setEditingId(null)}>
                    {copy.cancel}
                  </button>
                </div>
              </form>
            ) : (
              <>
                <button
                  aria-current={conversation.id === selectedId ? "true" : undefined}
                  className="chat-history__select"
                  type="button"
                  onClick={() => onSelect(conversation.id)}
                >
                  {conversation.title}
                </button>
                {authenticated ? (
                  <div className="chat-history__actions">
                    <button type="button" onClick={() => startRename(conversation)}>
                      {copy.rename}
                    </button>
                    <button type="button" onClick={() => onArchive(conversation.id)}>
                      {copy.archive}
                    </button>
                  </div>
                ) : null}
              </>
            )}
          </li>
        ))}
      </ol>
      {!authenticated && conversations.length > 0 ? (
        <button
          aria-label={copy.startFresh}
          className="chat-history__fresh"
          type="button"
          onClick={onStartFresh}
        >
          {copy.startFresh} →
        </button>
      ) : null}
    </aside>
  );
}
