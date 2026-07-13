import { expect, test } from "@playwright/test";

const SYMBOLS = [
  "AAPL",
  "MSFT",
  "NVDA",
  "AMZN",
  "GOOGL",
  "META",
  "TSLA",
  "JPM",
  "XOM",
  "COST",
  "NFLX",
];

test.beforeEach(async ({ page, request }) => {
  await request.post("http://127.0.0.1:8001/__e2e__/reset");
  await installFakeGoogle(page);
});

test("guest completes bilingual evidence-first company research", async ({
  page,
}) => {
  await page.goto("/en-US/dashboard");
  const search = page.getByRole("combobox", { name: "Search companies" });
  await search.fill("Apple");
  await expect(page.getByRole("option", { name: /AAPL Apple Inc/ })).toBeVisible();
  await search.press("ArrowDown");
  await search.press("Enter");

  await expect(page).toHaveURL(/\/en-US\/companies\/AAPL$/);
  await expect(page.getByRole("heading", { name: "Apple Inc." })).toBeVisible();
  await expect(page.getByText("$212.48")).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "TTM" })).toBeVisible();
  await expect(page.getByText("Price history")).toHaveCount(0);

  await page.getByRole("button", { name: "Run agent analysis" }).click();
  await expect(page.getByText("Queued")).toBeVisible();
  await expect(page.getByText(/1 daily analyses remaining/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Upstream" })).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText("Analysis complete")).toBeVisible();

  const lanes = page.locator(".evidence-flow__lane");
  for (let index = 0; index < 3; index += 1) {
    await lanes.nth(index).getByRole("button", { name: /Citation/ }).click();
    await expect(
      page.getByRole("dialog", { name: "Source evidence" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Close evidence" }).last().click();
  }

  await page.getByRole("combobox", { name: "Language" }).selectOption("zh-CN");
  await expect(page).toHaveURL(/\/zh-CN\/companies\/AAPL$/);
  await expect(page.getByRole("heading", { name: "上游" })).toBeVisible();
  await expect(page.getByText("测试：Manufacturing supply")).toBeVisible();
  await expect(page.getByRole("button", { name: "运行 Agent 分析" })).toBeVisible();
  await page.reload();
  await expect(page.getByText(/1.*次今日分析剩余/)).toBeVisible();
});

test("authenticated watchlist persists and ten-analysis limit is enforced", async ({
  page,
}) => {
  await page.goto("/en-US/login");
  await page.getByRole("button", { name: "Continue with Google" }).click();
  await expect(page).toHaveURL(/\/en-US\/dashboard$/);

  await page.getByRole("textbox", { name: "Add ticker" }).fill("AAPL");
  await page.getByRole("button", { name: "Add" }).click();
  await expect(page.getByText("Company added to your watchlist.")).toBeAttached();
  await page.reload();
  await expect(page.getByRole("link", { name: /AAPL Apple Inc/ })).toBeVisible();
  await page.getByRole("button", { name: "Remove AAPL" }).click();
  await expect(page.getByText("No saved companies yet. Add a ticker to begin.")).toBeVisible();

  const statuses = await page.evaluate(async (symbols) => {
    const result: number[] = [];
    for (const symbol of symbols) {
      const response = await fetch(`/api/research/companies/${symbol}/sync`, {
        method: "POST",
      });
      result.push(response.status);
    }
    return result;
  }, SYMBOLS);
  expect(statuses.slice(0, 10)).toEqual(Array(10).fill(202));
  expect(statuses[10]).toBe(429);

  await page.goto("/en-US/companies/NFLX");
  await page.getByRole("button", { name: "Run agent analysis" }).click();
  await expect(page.getByText(/Daily allowance used/)).toBeVisible();
  await expect(page.getByRole("link", { name: /Sign in for/ })).toHaveCount(0);
});

async function installFakeGoogle(page: import("@playwright/test").Page) {
  await page.route("https://accounts.google.com/gsi/client", (route) =>
    route.fulfill({
      body: "",
      contentType: "application/javascript",
      status: 200,
    }),
  );
  await page.addInitScript(() => {
    let callback: (response: { credential: string }) => void = () => undefined;
    Object.assign(window, {
      google: {
        accounts: {
          id: {
            initialize: (config: { callback: typeof callback }) => {
              callback = config.callback;
            },
            renderButton: (parent: HTMLElement) => {
              const button = document.createElement("button");
              button.textContent = "Continue with Google";
              button.addEventListener("click", () =>
                callback({ credential: "e2e-google-token" }),
              );
              parent.replaceChildren(button);
            },
          },
        },
      },
    });
  });
}
