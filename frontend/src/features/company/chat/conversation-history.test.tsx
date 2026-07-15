import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { companyPageCopy } from "../copy";
import { ConversationHistory } from "./conversation-history";

const conversations = [
  {
    id: "11111111-1111-4111-8111-111111111111",
    company_id: 1,
    title: "Margins",
    locale: "en-US" as const,
    expires_at: null,
    archived_at: null,
    created_at: "2026-07-15T00:00:00Z",
    updated_at: "2026-07-15T01:00:00Z",
  },
  {
    id: "22222222-2222-4222-8222-222222222222",
    company_id: 1,
    title: "Supply chain",
    locale: "en-US" as const,
    expires_at: null,
    archived_at: null,
    created_at: "2026-07-14T00:00:00Z",
    updated_at: "2026-07-14T01:00:00Z",
  },
];

describe("ConversationHistory", () => {
  afterEach(cleanup);

  it("supports authenticated selection, creation, rename, and archive", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const onNew = vi.fn();
    const onRename = vi.fn();
    const onArchive = vi.fn();

    render(
      <ConversationHistory
        authenticated
        conversations={conversations}
        copy={companyPageCopy.en.chat}
        onArchive={onArchive}
        onNew={onNew}
        onRename={onRename}
        onSelect={onSelect}
        onStartFresh={vi.fn()}
        selectedId={conversations[0].id}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Supply chain" }));
    expect(onSelect).toHaveBeenCalledWith(conversations[1].id);
    await user.click(screen.getByRole("button", { name: companyPageCopy.en.chat.newConversation }));
    expect(onNew).toHaveBeenCalledOnce();
    await user.click(screen.getAllByRole("button", { name: companyPageCopy.en.chat.rename })[0]);
    const input = screen.getByRole("textbox", { name: companyPageCopy.en.chat.conversationTitle });
    await user.clear(input);
    await user.type(input, "Profitability");
    await user.click(screen.getByRole("button", { name: companyPageCopy.en.chat.saveTitle }));
    expect(onRename).toHaveBeenCalledWith(conversations[0].id, "Profitability");
    await user.click(screen.getAllByRole("button", { name: companyPageCopy.en.chat.archive })[0]);
    expect(onArchive).toHaveBeenCalledWith(conversations[0].id);
  });

  it("gives guests one archive-and-start-fresh action", async () => {
    const user = userEvent.setup();
    const onStartFresh = vi.fn();

    render(
      <ConversationHistory
        authenticated={false}
        conversations={conversations.slice(0, 1)}
        copy={companyPageCopy.en.chat}
        onArchive={vi.fn()}
        onNew={vi.fn()}
        onRename={vi.fn()}
        onSelect={vi.fn()}
        onStartFresh={onStartFresh}
        selectedId={conversations[0].id}
      />,
    );

    expect(screen.queryByRole("button", { name: companyPageCopy.en.chat.rename })).toBeNull();
    await user.click(screen.getByRole("button", { name: companyPageCopy.en.chat.startFresh }));
    expect(onStartFresh).toHaveBeenCalledOnce();
  });
});
