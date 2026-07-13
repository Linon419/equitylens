import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page, request }) => {
  await request.post("http://127.0.0.1:8001/__e2e__/reset");
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
});

test("signs in, refreshes, changes locale, and signs out", async ({
  page,
}) => {
  await page.goto("/en-US/login");
  await page.getByRole("button", { name: "Continue with Google" }).click();
  await expect(page).toHaveURL(/\/en-US\/dashboard$/);
  await expect(
    page.getByRole("heading", { name: "Understand the company behind the ticker." }),
  ).toBeVisible();

  const refreshStatus = await page.evaluate(async () =>
    fetch("/api/auth/refresh", { method: "POST" }).then(
      (response) => response.status,
    ),
  );
  expect(refreshStatus).toBe(200);

  await page.goto("/en-US/settings");
  await page.getByRole("combobox").last().selectOption("zh-CN");
  await expect(page).toHaveURL(/\/zh-CN\/settings$/);
  await expect
    .poll(() =>
      page.evaluate(async () => {
        const response = await fetch("/api/auth/me");
        const user = await response.json();
        return user.preferred_locale;
      }),
    )
    .toBe("zh-CN");

  await page.getByRole("button", { name: "退出登录" }).click();
  await expect(page).toHaveURL(/\/zh-CN$/);
});

test("redirects a signed-out user from a protected route", async ({
  browser,
}) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto("/en-US/settings");
  await expect(page).toHaveURL(
    /\/en-US\/login\?returnTo=%2Fen-US%2Fsettings$/,
  );
  await context.close();
});
