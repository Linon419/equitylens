"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import { parseChatEventStream } from "@/lib/chat/sse";
import type {
  ChatContextSelection,
  ChatConversation,
  ChatLocale,
  ChatQuotaStatus,
  ChatReadiness,
  SelectedChatContext,
} from "@/lib/chat/types";
import {
  ChatRequestError,
  createRemoteConversation,
  getJson,
  getMessagePage,
  isAbort,
  mutate,
  mutationJson,
  requestStream,
} from "./chat-api";
import { chatStreamReducer, INITIAL_STREAM } from "./chat-state";

export function useCompanyChat({
  locale,
  open,
  symbol,
}: {
  locale: ChatLocale;
  open: boolean;
  symbol: string;
}) {
  const [stream, dispatch] = useReducer(chatStreamReducer, INITIAL_STREAM);
  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [readiness, setReadiness] = useState<ChatReadiness | null>(null);
  const [contexts, setContexts] = useState<SelectedChatContext[]>([]);
  const [loading, setLoading] = useState(open);
  const streamController = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!open) {
      streamController.current?.abort();
      return;
    }
    const controller = new AbortController();
    void Promise.resolve().then(async () => {
      if (controller.signal.aborted) return;
      setLoading(true);
      void loadAuxiliary(controller.signal);
      await bootstrapHistory(controller.signal);
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => {
      controller.abort();
      streamController.current?.abort();
    };

    async function bootstrapHistory(signal: AbortSignal) {
      try {
        const initialConversations = await getJson<ChatConversation[]>(
          `/api/research/companies/${symbol}/conversations`,
          signal,
        );
        let available = initialConversations;
        if (available.length === 0) {
          available = [await createRemoteConversation(symbol, locale, signal)];
        }
        const stored = localStorage.getItem(storageKey(symbol));
        const selected = available.find((item) => item.id === stored) ?? available[0];
        setConversations(available);
        setSelectedId(selected.id);
        localStorage.setItem(storageKey(symbol), selected.id);
        const page = await getMessagePage(selected.id, null, signal);
        setNextCursor(page.next_cursor);
        dispatch({ type: "messages", items: page.items });
      } catch (error) {
        if (!isAbort(error)) {
          dispatch({ type: "transport_error", code: "CHAT_LOAD_FAILED" });
        }
      }
    }

    async function loadAuxiliary(signal: AbortSignal) {
      const [quotaResult, readinessResult] = await Promise.allSettled([
        getJson<ChatQuotaStatus>("/api/research/chat-quota", signal),
        getJson<ChatReadiness>(
          `/api/research/companies/${symbol}/chat-readiness?locale=${locale}`,
          signal,
        ),
      ]);
      if (signal.aborted) return;
      if (quotaResult.status === "fulfilled") {
        dispatch({ type: "quota", quota: quotaResult.value });
      }
      if (readinessResult.status === "fulfilled") {
        setReadiness(readinessResult.value);
      }
    }
  }, [locale, open, symbol]);

  const selectConversation = useCallback(async (id: string) => {
    streamController.current?.abort();
    setLoading(true);
    try {
      const page = await getMessagePage(id);
      setSelectedId(id);
      setNextCursor(page.next_cursor);
      localStorage.setItem(storageKey(symbol), id);
      dispatch({ type: "messages", items: page.items });
    } catch (error) {
      if (!isAbort(error)) {
        dispatch({ type: "transport_error", code: "CHAT_LOAD_FAILED" });
      }
    } finally {
      setLoading(false);
    }
  }, [symbol]);

  const createConversation = useCallback(async () => {
    setLoading(true);
    try {
      const created = await createRemoteConversation(symbol, locale);
      setConversations((current) => [created, ...current]);
      setSelectedId(created.id);
      setNextCursor(null);
      localStorage.setItem(storageKey(symbol), created.id);
      dispatch({ type: "messages", items: [] });
    } finally {
      setLoading(false);
    }
  }, [locale, symbol]);

  const renameConversation = useCallback(async (id: string, title: string) => {
    const renamed = await mutationJson<ChatConversation>(
      `/api/research/conversations/${id}`,
      { method: "PATCH", body: JSON.stringify({ title }) },
    );
    setConversations((current) =>
      current.map((item) => (item.id === id ? renamed : item)),
    );
  }, []);

  const archiveConversation = useCallback(async (id: string) => {
    await mutate(`/api/research/conversations/${id}`, { method: "DELETE" });
    const remaining = conversations.filter((item) => item.id !== id);
    setConversations(remaining);
    if (selectedId === id) {
      if (remaining[0]) await selectConversation(remaining[0].id);
      else {
        setSelectedId(null);
        setNextCursor(null);
        dispatch({ type: "messages", items: [] });
      }
    }
  }, [conversations, selectConversation, selectedId]);

  const startFresh = useCallback(async () => {
    if (selectedId) {
      await mutate(`/api/research/conversations/${selectedId}`, { method: "DELETE" });
    }
    setConversations([]);
    await createConversation();
  }, [createConversation, selectedId]);

  const loadMore = useCallback(async () => {
    if (!selectedId || !nextCursor) return;
    const page = await getMessagePage(selectedId, nextCursor);
    setNextCursor(page.next_cursor);
    dispatch({ type: "messages", items: page.items, append: true });
  }, [nextCursor, selectedId]);

  const refreshReadiness = useCallback(async () => {
    try {
      setReadiness(
        await getJson<ChatReadiness>(
          `/api/research/companies/${symbol}/chat-readiness?locale=${locale}`,
        ),
      );
    } catch (error) {
      if (!isAbort(error)) {
        dispatch({ type: "transport_error", code: "CHAT_LOAD_FAILED" });
      }
    }
  }, [locale, symbol]);

  const runStream = useCallback(async (
    path: string,
    body: string,
    question?: string,
  ) => {
    const controller = new AbortController();
    streamController.current?.abort();
    streamController.current = controller;
    dispatch({ type: "start" });
    let accepted = false;
    let terminal = false;
    try {
      const response = await requestStream(path, body, controller.signal);
      for await (const event of parseChatEventStream(response.body!, controller.signal)) {
        accepted ||= event.kind === "accepted";
        terminal ||= event.kind === "complete" || event.kind === "error";
        dispatch({ type: "event", event, question, locale });
      }
      if (accepted && !terminal && selectedId) {
        const page = await getMessagePage(selectedId, null, controller.signal);
        setNextCursor(page.next_cursor);
        dispatch({ type: "messages", items: page.items });
      } else if (!terminal) {
        dispatch({ type: "transport_error", code: "CHAT_STREAM_INTERRUPTED" });
      }
    } catch (error) {
      if (!isAbort(error)) {
        dispatch({
          type: "transport_error",
          code: error instanceof ChatRequestError
            ? error.code
            : "CHAT_STREAM_INTERRUPTED",
        });
      }
    } finally {
      if (streamController.current === controller) streamController.current = null;
    }
  }, [locale, selectedId]);

  const send = useCallback(async (content: string) => {
    if (!selectedId || stream.streaming) return;
    const body = JSON.stringify({
      client_request_id: crypto.randomUUID(),
      content,
      locale,
      context: contexts.map(
        (item) => item.selection satisfies ChatContextSelection,
      ),
    });
    setContexts([]);
    await runStream(
      `/api/research/conversations/${selectedId}/messages`,
      body,
      content,
    );
  }, [contexts, locale, runStream, selectedId, stream.streaming]);

  const retry = useCallback(async (assistantMessageId: string) => {
    if (!selectedId || stream.streaming) return;
    await runStream(
      `/api/research/conversations/${selectedId}/messages/${assistantMessageId}/retry`,
      JSON.stringify({ client_request_id: crypto.randomUUID() }),
    );
  }, [runStream, selectedId, stream.streaming]);

  const addContext = useCallback((context: SelectedChatContext) => {
    setContexts((current) =>
      current.some((item) => item.key === context.key)
        ? current
        : [...current, context],
    );
  }, []);

  return {
    ...stream,
    addContext,
    archiveConversation,
    clearContexts: () => setContexts([]),
    contexts,
    conversations,
    createConversation,
    loadMore,
    loading,
    nextCursor,
    readiness,
    refreshReadiness,
    removeContext: (key: string) =>
      setContexts((current) => current.filter((item) => item.key !== key)),
    renameConversation,
    retry,
    selectedConversation:
      conversations.find((item) => item.id === selectedId) ?? null,
    selectedId,
    selectConversation,
    send,
    startFresh,
  };
}

function storageKey(symbol: string) {
  return `equitylens:chat:${symbol}:active`;
}
