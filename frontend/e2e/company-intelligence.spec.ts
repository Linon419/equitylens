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
  await expect(page.getByRole("heading", { name: "Key businesses" })).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText("Analysis complete")).toBeVisible();

  await page.getByRole("button", { name: /Citation/ }).first().click();
  await expect(
    page.getByRole("dialog", { name: "Source evidence" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close evidence" }).last().click();

  await page.getByRole("combobox", { name: "Language" }).selectOption("zh-CN");
  await expect(page).toHaveURL(/\/zh-CN\/companies\/AAPL$/);
  await expect(page.getByRole("heading", { name: "关键业务" })).toBeVisible();
  await expect(page.getByText("测试：Devices and services")).toBeVisible();
  await expect(page.getByRole("button", { name: "运行 Agent 分析" })).toBeVisible();
  await page.reload();
  await expect(page.getByText(/1.*次今日分析剩余/)).toBeVisible();
});

test("guest generates and explores an evidence-backed supply chain graph", async ({
  page,
}) => {
  await page.goto("/en-US/companies/AAPL");
  await page.getByRole("button", { name: "Generate graph" }).click();
  await expect(page.getByText("Queued")).toBeVisible();
  await expect(page.getByText("Collecting official sources")).toBeVisible({
    timeout: 8_000,
  });
  await expect(
    page.getByRole("button", { name: /Select Apple Inc\./ }),
  ).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/1 daily graph runs remaining/)).toBeVisible();

  await page.getByRole("button", { name: "Relationship list" }).click();
  await page.getByRole("button", {
    name: /TSMC Semiconductor Manufacturing Supplies Apple Silicon.*Verified relationship/i,
  }).click();
  await expect(
    page.getByRole("heading", { name: "Relationship evidence" }),
  ).toBeVisible();
  await expect(page.getByText(/TSMC Semiconductor Manufacturing fabricates/)).toBeVisible();
  await expect(page.getByRole("link", { name: "Open official source" })).toHaveAttribute(
    "href",
    /apple\.com/,
  );

  await page.getByRole("button", { name: "Close evidence" }).click();
  await page.getByRole("switch", { name: "Potential relationships" }).click();
  await expect(page.getByRole("button", {
    name: /SK hynix Memory Supplies Apple Silicon.*Potential relationship/i,
  })).toBeVisible();

  await page.reload();
  await expect(page.getByText(/1 daily graph runs remaining/)).toBeVisible();
  await expect(page.getByText(/Apple combines a concentrated component/)).toBeVisible();

  await page.getByRole("combobox", { name: "Language" }).selectOption("zh-CN");
  await expect(page).toHaveURL(/\/zh-CN\/companies\/AAPL$/);
  await expect(page.getByRole("heading", { name: "AI 产业链图谱" })).toBeVisible();
  await expect(page.getByRole("button", {
    name: /选择 中文 TSMC Semiconductor Manufacturing \(TSM\)/,
  })).toBeVisible();
  await page.getByRole("button", { name: "关系列表" }).click();
  const localizedRelationship = page.getByRole("button", {
    name: /中文 TSMC Semiconductor Manufacturing 供应 中文 Apple Silicon.*已核验关系/i,
  });
  await localizedRelationship.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByText(
    "TSMC Semiconductor Manufacturing fabricates Apple-designed silicon used across Apple products.",
  )).toBeVisible();
  await expect(page.getByRole("link", { name: "打开官方来源" })).toHaveAttribute(
    "href",
    /apple\.com/,
  );
});

test("graph refresh failure preserves the cited snapshot and refunds quota", async ({
  page,
}) => {
  await generateAppleGraph(page);
  const thesis = /Apple combines a concentrated component/;
  await expect(page.getByText(thesis)).toBeVisible();

  await page.getByRole("button", { name: "Refresh graph" }).click();
  await expect(page.getByText("Queued")).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry graph research" })).toBeVisible({
    timeout: 8_000,
  });
  await expect(page.getByText(thesis)).toBeVisible();
  await expect(page.getByText(/1 daily graph runs remaining/)).toBeVisible();
});

test("guest graph quota counts completed jobs and cached reuse costs zero", async ({
  page,
}) => {
  await page.goto("/en-US/companies/AAPL");
  const result = await page.evaluate(async () => {
    const sync = async (symbol: string) => {
      const response = await fetch(
        `/api/research/companies/${symbol}/supply-chain-graph/sync`,
        {
          body: JSON.stringify({ force_refresh: false }),
          headers: { "content-type": "application/json" },
          method: "POST",
        },
      );
      return { body: await response.json(), status: response.status };
    };
    const waitForCompletion = async (jobId: string) => {
      for (let attempt = 0; attempt < 60; attempt += 1) {
        const response = await fetch(`/api/research/jobs/${jobId}`);
        const job = await response.json();
        if (["completed", "failed"].includes(job.state)) return job;
        await new Promise((resolve) => window.setTimeout(resolve, 250));
      }
      throw new Error("graph job did not reach a terminal state");
    };

    const first = await sync("AAPL");
    const firstJob = await waitForCompletion(first.body.job.id);
    const cached = await sync("AAPL");
    const second = await sync("MSFT");
    const secondJob = await waitForCompletion(second.body.job.id);
    const limited = await sync("NVDA");
    return { cached, first, firstJob, limited, second, secondJob };
  });

  expect(result.first.status).toBe(202);
  expect(result.firstJob.state).toBe("completed");
  expect(result.cached.status).toBe(200);
  expect(result.cached.body.status).toBe("reused_snapshot");
  expect(result.cached.body.quota.remaining).toBe(1);
  expect(result.second.status).toBe(202);
  expect(result.secondJob.state).toBe("completed");
  expect(result.limited.status).toBe(429);
});

test("mobile users start in the relationship list and can open evidence", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await generateAppleGraph(page);

  await expect(page.getByRole("button", { name: "Relationship list" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await page.getByRole("button", {
    name: /TSMC Semiconductor Manufacturing Supplies Apple Silicon.*Verified relationship/i,
  }).click();
  await expect(page.locator(".supply-chain-inspector")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Relationship evidence" })).toBeVisible();
});

test("a resolved neighbor can become the next research center", async ({ page }) => {
  await generateAppleGraph(page);
  await page.getByRole("button", {
    name: /Select TSMC Semiconductor Manufacturing \(TSM\)/,
  }).click();
  await page.getByRole("button", { name: "Center on this company" }).click();
  await expect(page).toHaveURL(/\/en-US\/companies\/TSM$/);
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

async function generateAppleGraph(page: import("@playwright/test").Page) {
  await page.goto("/en-US/companies/AAPL");
  await page.getByRole("button", { name: "Generate graph" }).click();
  await expect(
    page.getByText(/Apple combines a concentrated component/),
  ).toBeVisible({ timeout: 15_000 });
}
