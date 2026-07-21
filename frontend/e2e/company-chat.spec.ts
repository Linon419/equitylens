import { expect, test, type Page } from "@playwright/test";

const APP = "http://127.0.0.1:3000";

test.beforeEach(async ({ page, request }) => {
  await request.post("http://127.0.0.1:8001/__e2e__/reset");
  await installFakeGoogle(page);
});

test("guest completes two messages and receives a third-message 429", async ({ page }) => {
  await page.goto("/en-US/companies/AAPL");
  const conversationId = await createConversation(page, "en-US");
  const first = await postMessage(page, conversationId, crypto.randomUUID(), "FY2025 revenue");
  const second = await postMessage(page, conversationId, crypto.randomUUID(), "Gross margin");
  const third = await postMessage(page, conversationId, crypto.randomUUID(), "One more question");

  expect([first.status, second.status, third.status]).toEqual([200, 200, 429]);
  expect(ssePayload(second.body, "complete").quota.remaining).toBe(0);
  expect(JSON.parse(third.body).code).toBe("CHAT_DAILY_QUOTA_EXCEEDED");
});

test("repeated request ID replays without extra usage", async ({ page }) => {
  await page.goto("/en-US/companies/AAPL");
  const conversationId = await createConversation(page, "en-US");
  const requestId = crypto.randomUUID();
  const first = await postMessage(page, conversationId, requestId, "FY2025 filing revenue");
  const replay = await postMessage(page, conversationId, requestId, "FY2025 filing revenue");
  const quota = await page.evaluate(async () =>
    (await fetch("/api/research/chat-quota")).json(),
  );

  expect(ssePayload(first.body, "complete").message.id).toBe(
    ssePayload(replay.body, "complete").message.id,
  );
  expect(quota.used).toBe(1);
});

test("filing question completes with internal evidence and no web citation", async ({ page }) => {
  const dialog = await openChat(page, "en-US");
  await ask(dialog, "What were Apple's FY2025 revenue and gross margin?", "Send question");

  await expect(dialog.getByText("Evidence coverage: complete")).toBeVisible();
  await dialog.getByText("Cited sources", { exact: true }).click();
  await expect(dialog.getByRole("link", { name: /AAPL Revenue/ })).toBeVisible();
  await expect(dialog.getByRole("link", { name: /FTC competition update/ })).toHaveCount(0);
});

test("current-event question includes web tier and date metadata", async ({ page }) => {
  const dialog = await openChat(page, "en-US");
  await ask(dialog, "What is Apple's current regulatory risk?", "Send question");

  await dialog.getByText("Cited sources", { exact: true }).click();
  const source = dialog.getByRole("link", { name: /FTC competition update/ });
  await expect(source).toBeVisible();
  const citation = source.locator("xpath=ancestor::li");
  await expect(citation).toContainText("Primary source");
  await expect(citation).toContainText("2026-07-14");
});

test("graph relationship action opens chat with an approved context chip", async ({ page }) => {
  await generateAppleGraph(page);
  await page.getByRole("button", { name: "Relationship list" }).click();
  await page.getByRole("button", {
    name: /TSMC Semiconductor Manufacturing Supplies Apple Silicon.*Verified relationship/i,
  }).click();
  await page.getByRole("button", {
    name: "Ask EquityLens about this relationship",
  }).click();

  const dialog = page.getByRole("dialog", { name: "Ask EquityLens" });
  await expect(dialog).toBeVisible();
  const context = dialog.getByRole("region", { name: "Selected page context" });
  await expect(context).toContainText("TSMC Semiconductor Manufacturing");
  await ask(dialog, "Explain this relationship.", "Send question");
  await expect(dialog.getByText("Evidence coverage: complete")).toBeVisible();
});

test("model failure refunds quota and retry completes once", async ({ page }) => {
  const dialog = await openChat(page, "en-US");
  await ask(dialog, "Force model failure while analyzing FY2025 revenue", "Send question");
  await expect(dialog.getByRole("button", { name: "Retry answer" })).toBeVisible();
  await expect(dialog.getByText(/2 messages remaining/)).toBeVisible();

  await dialog.getByRole("button", { name: "Retry answer" }).click();
  await expect(dialog.getByText("Evidence coverage: complete")).toBeVisible();
  await expect(dialog.getByText(/1 message remaining/)).toBeVisible();
});

test("Chinese locale streams localized stages and answer sections", async ({ page }) => {
  const dialog = await openChat(page, "zh-CN");
  const composer = dialog.getByRole("textbox", { name: "投研问题" });
  await composer.fill("苹果近期有哪些监管变化？");
  await dialog.getByRole("button", { name: "发送问题" }).click();
  await expect(dialog.getByText("正在检索公司证据")).toBeVisible();
  await expect(dialog.getByRole("heading", { name: "直接结论" })).toBeVisible();
  await expect(dialog.getByText(/苹果 FY2025 营收为/)).toBeVisible();
});

test("authenticated conversations can be created renamed archived and reloaded", async ({ page }) => {
  await page.goto("/en-US/login");
  await page.getByRole("button", { name: "Continue with Google" }).click();
  await expect(page).toHaveURL(/\/en-US\/dashboard$/);
  const dialog = await openChat(page, "en-US");
  await dialog.getByRole("button", { name: "Conversation history" }).click();
  await dialog.getByRole("button", { name: "New conversation" }).click();
  await expect(dialog.locator(".chat-history li")).toHaveCount(2);
  const firstConversation = dialog.locator(".chat-history li").first();
  await firstConversation.getByRole("button", { name: "Rename conversation" }).click();
  await firstConversation.getByRole("textbox", { name: "Conversation title" }).fill("Apple moat review");
  await firstConversation.getByRole("button", { name: "Save title" }).click();
  await expect(
    dialog.getByRole("heading", { name: "Apple moat review" }),
  ).toBeVisible();

  await page.reload();
  const reopened = await openChatOnCurrentPage(page, "en-US");
  await reopened.getByRole("button", { name: "Conversation history" }).click();
  const renamed = reopened.locator(".chat-history li").filter({ hasText: "Apple moat review" });
  await expect(renamed).toBeVisible();
  await renamed.getByRole("button", { name: "Archive conversation" }).click();
  await expect(reopened.getByText("Apple moat review")).toHaveCount(0);
});

test("a second authenticated user receives 404 for another user's conversation", async ({ browser }) => {
  const firstContext = await browser.newContext();
  const secondContext = await browser.newContext();
  const firstPage = await firstContext.newPage();
  const secondPage = await secondContext.newPage();
  await installFakeGoogle(firstPage, "e2e-google-token");
  await installFakeGoogle(secondPage, "e2e-google-token-2");
  await firstPage.goto(`${APP}/en-US/login`);
  await secondPage.goto(`${APP}/en-US/login`);
  await firstPage.getByRole("button", { name: "Continue with Google" }).click();
  await secondPage.getByRole("button", { name: "Continue with Google" }).click();
  await expect(firstPage).toHaveURL(/\/en-US\/dashboard$/);
  await expect(secondPage).toHaveURL(/\/en-US\/dashboard$/);
  const conversationId = await createConversation(firstPage, "en-US");
  const status = await secondPage.evaluate(async (id) =>
    (await fetch(`/api/research/conversations/${id}`)).status, conversationId,
  );

  expect(status).toBe(404);
  await firstContext.close();
  await secondContext.close();
});

test("desktop chat is visible by default and fits below the app header", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/en-US/companies/AAPL");
  const dialog = page.getByRole("dialog", { name: "Ask EquityLens" });
  await expect(dialog).toBeVisible();
  const box = await dialog.boundingBox();
  expect(box?.y).toBe(82);
  expect((box?.y ?? 0) + (box?.height ?? 0)).toBeLessThanOrEqual(900);
  await expect(dialog.getByRole("textbox", { name: "Research question" })).toBeEnabled();
});

test("mobile chat supports keyboard citations and restores launcher focus", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/en-US/companies/AAPL");
  const dialog = page.getByRole("dialog", { name: "Ask EquityLens" });
  await expect(dialog).toBeHidden();
  const launcher = page.getByRole("button", { name: "Ask EquityLens", exact: true });
  await launcher.focus();
  await launcher.click();
  await expect(dialog).toBeVisible();
  const box = await dialog.boundingBox();
  expect(box?.height).toBeLessThanOrEqual(779);
  await expect(dialog.getByRole("textbox", { name: "Research question" })).toBeEnabled();
  await ask(dialog, "What was Apple's FY2025 revenue?", "Send question");
  await dialog.getByText("Cited sources", { exact: true }).click();
  const citation = dialog.getByRole("link", { name: /AAPL Revenue/ });
  await citation.focus();
  await expect(citation).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(launcher).toBeFocused();
});

async function openChat(page: Page, locale: "en-US" | "zh-CN") {
  await page.goto(`/${locale}/companies/AAPL`);
  return openChatOnCurrentPage(page, locale);
}

async function openChatOnCurrentPage(page: Page, locale: "en-US" | "zh-CN") {
  const name = locale === "zh-CN" ? "询问 EquityLens" : "Ask EquityLens";
  const dialog = page.getByRole("dialog", { name });
  if (!(await dialog.isVisible())) {
    await page.getByRole("button", { name, exact: true }).click();
  }
  await expect(dialog).toBeVisible();
  const question = locale === "zh-CN" ? "投研问题" : "Research question";
  await expect(dialog.getByRole("textbox", { name: question })).toBeEnabled({
    timeout: 10_000,
  });
  return dialog;
}

async function ask(dialog: ReturnType<Page["getByRole"]>, question: string, send: string) {
  await dialog.getByRole("textbox").fill(question);
  await dialog.getByRole("button", { name: send }).click();
  await expect(dialog.getByText(question)).toBeVisible();
}

async function createConversation(page: Page, locale: "en-US" | "zh-CN") {
  return page.evaluate(async ({ locale }) => {
    const response = await fetch("/api/research/companies/AAPL/conversations", {
      body: JSON.stringify({ locale }),
      headers: { "content-type": "application/json" },
      method: "POST",
    });
    return (await response.json()).id as string;
  }, { locale });
}

async function postMessage(
  page: Page,
  conversationId: string,
  requestId: string,
  question: string,
) {
  return page.evaluate(async ({ conversationId, question, requestId }) => {
    const response = await fetch(`/api/research/conversations/${conversationId}/messages`, {
      body: JSON.stringify({
        client_request_id: requestId,
        content: question,
        context: [],
        locale: "en-US",
      }),
      headers: { accept: "text/event-stream", "content-type": "application/json" },
      method: "POST",
    });
    return { body: await response.text(), status: response.status };
  }, { conversationId, question, requestId });
}

function ssePayload(body: string, kind: string) {
  const block = body.split("\n\n").find((item) => item.includes(`event: ${kind}\n`));
  const data = block?.split("\n").find((line) => line.startsWith("data: "))?.slice(6);
  if (!data) throw new Error(`Missing ${kind} SSE event`);
  return JSON.parse(data);
}

async function generateAppleGraph(page: Page) {
  await page.goto("/en-US/companies/AAPL");
  await page.getByRole("button", { name: "Generate graph" }).click();
  await expect(page.getByText(/Apple combines a concentrated component/)).toBeVisible({
    timeout: 15_000,
  });
}

async function installFakeGoogle(page: Page, credential = "e2e-google-token") {
  await page.route("https://accounts.google.com/gsi/client", (route) =>
    route.fulfill({ body: "", contentType: "application/javascript", status: 200 }),
  );
  await page.addInitScript((token) => {
    let callback: (response: { credential: string }) => void = () => undefined;
    Object.assign(window, {
      google: { accounts: { id: {
        initialize: (config: { callback: typeof callback }) => { callback = config.callback; },
        renderButton: (parent: HTMLElement) => {
          const button = document.createElement("button");
          button.textContent = "Continue with Google";
          button.addEventListener("click", () => callback({ credential: token }));
          parent.replaceChildren(button);
        },
      } } },
    });
  }, credential);
}
