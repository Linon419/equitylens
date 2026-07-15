import { describe, expect, it } from "vitest";

import { parseChatEventStream } from "./sse";

const accepted = {
  user_message_id: "11111111-1111-4111-8111-111111111111",
  assistant_message_id: "22222222-2222-4222-8222-222222222222",
  conversation_id: "33333333-3333-4333-8333-333333333333",
  quota: {
    limit: 2,
    used: 1,
    remaining: 1,
    resets_at: "2026-07-16T00:00:00Z",
  },
};

describe("parseChatEventStream", () => {
  it("decodes UTF-8 splits, comments, multiple frames, and multiline data", async () => {
    const first = frame(1, "accepted", accepted);
    const sectionPayload = JSON.stringify({
      section: "direct_conclusion",
      delta: "苹果业务",
    });
    const split = sectionPayload.indexOf('"delta"');
    const second = [
      ": heartbeat",
      "id: 2",
      "event: section",
      `data: ${sectionPayload.slice(0, split)}`,
      `data: ${sectionPayload.slice(split)}`,
      "",
      "",
    ].join("\n");
    const bytes = new TextEncoder().encode(first + second);
    const chinese = new TextEncoder().encode("苹果");
    const boundary = findSubarray(bytes, chinese) + 1;
    const stream = chunks(bytes.slice(0, boundary), bytes.slice(boundary));

    const events = await collect(parseChatEventStream(stream));

    expect(events).toEqual([
      { id: 1, kind: "accepted", payload: accepted },
      {
        id: 2,
        kind: "section",
        payload: { section: "direct_conclusion", delta: "苹果业务" },
      },
    ]);
  });

  it.each([
    ["invalid JSON", "id: 1\nevent: stage\ndata: {bad}\n\n", "Invalid SSE JSON"],
    [
      "unknown event",
      "id: 1\nevent: secret\ndata: {}\n\n",
      "Unknown chat event",
    ],
    [
      "non-monotonic ID",
      frame(2, "stage", { stage: "retrieval", status_key: "chat.stage.retrieval" }) +
        frame(2, "stage", { stage: "web", status_key: "chat.stage.web" }),
      "monotonic",
    ],
    [
      "invalid payload",
      frame(1, "stage", { stage: "unknown", status_key: "x" }),
      "Invalid stage payload",
    ],
    [
      "incomplete final frame",
      "id: 1\nevent: stage\ndata: {}",
      "Incomplete SSE frame",
    ],
  ])("rejects %s", async (_label, body, message) => {
    await expect(collect(parseChatEventStream(textStream(body)))).rejects.toThrow(
      message,
    );
  });

  it("cancels the reader and throws AbortError", async () => {
    let cancelled = false;
    const stream = new ReadableStream<Uint8Array>({
      pull() {
        return new Promise(() => undefined);
      },
      cancel() {
        cancelled = true;
      },
    });
    const controller = new AbortController();
    const iterator = parseChatEventStream(stream, controller.signal);
    const pending = iterator.next();

    controller.abort();

    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
    expect(cancelled).toBe(true);
  });
});

function frame(id: number, event: string, payload: unknown) {
  return `id: ${id}\nevent: ${event}\ndata: ${JSON.stringify(payload)}\n\n`;
}

function textStream(value: string) {
  return chunks(new TextEncoder().encode(value));
}

function chunks(...values: Uint8Array[]) {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const value of values) controller.enqueue(value);
      controller.close();
    },
  });
}

async function collect<T>(values: AsyncIterable<T>): Promise<T[]> {
  const result: T[] = [];
  for await (const value of values) result.push(value);
  return result;
}

function findSubarray(value: Uint8Array, target: Uint8Array): number {
  return value.findIndex((_, index) =>
    target.every((byte, offset) => value[index + offset] === byte),
  );
}
