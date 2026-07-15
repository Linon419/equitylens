import type {
  ChatConversation,
  ChatLocale,
  ChatMessagePage,
} from "@/lib/chat/types";

export async function requestStream(
  path: string,
  body: string,
  signal: AbortSignal,
) {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      const response = await fetch(path, {
        method: "POST",
        headers: { accept: "text/event-stream", "content-type": "application/json" },
        body,
        signal,
      });
      if (response.status >= 500 && attempt === 0) continue;
      if (!response.ok) throw await requestError(response);
      if (!response.body) throw new ChatRequestError("CHAT_STREAM_EMPTY");
      return response;
    } catch (error) {
      if (isAbort(error) || error instanceof ChatRequestError || attempt > 0) throw error;
    }
  }
  throw new ChatRequestError("CHAT_STREAM_INTERRUPTED");
}

export function getMessagePage(
  id: string,
  cursor?: string | null,
  signal?: AbortSignal,
) {
  const query = cursor ? `?limit=50&cursor=${encodeURIComponent(cursor)}` : "?limit=50";
  return getJson<ChatMessagePage>(
    `/api/research/conversations/${id}/messages${query}`,
    signal,
  );
}

export function createRemoteConversation(
  symbol: string,
  locale: ChatLocale,
  signal?: AbortSignal,
) {
  return mutationJson<ChatConversation>(
    `/api/research/companies/${symbol}/conversations`,
    {
      method: "POST",
      body: JSON.stringify({ locale }),
      signal,
    },
  );
}

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { cache: "no-store", signal });
  if (!response.ok) throw await requestError(response);
  return response.json() as Promise<T>;
}

export async function mutationJson<T>(path: string, init: RequestInit): Promise<T> {
  const response = await mutate(path, init);
  return response.json() as Promise<T>;
}

export async function mutate(path: string, init: RequestInit): Promise<Response> {
  const response = await fetch(path, {
    ...init,
    headers: { "content-type": "application/json", ...init.headers },
  });
  if (!response.ok) throw await requestError(response);
  return response;
}

async function requestError(response: Response): Promise<ChatRequestError> {
  const payload = (await response.json().catch(() => null)) as { code?: string } | null;
  return new ChatRequestError(payload?.code ?? `CHAT_HTTP_${response.status}`);
}

export class ChatRequestError extends Error {
  constructor(public code: string) {
    super(code);
  }
}

export function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}
