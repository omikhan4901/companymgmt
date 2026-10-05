import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, setPlan, signUp, watchCsp } from "./helpers";

/** Opens a page and checks it rendered: a main heading, no crash, no CSP breakage. */
async function opens(page: Page, path: string, heading: string | RegExp) {
  await page.goto(path);
  await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
  await expect(page.getByText("Something went wrong")).toHaveCount(0);
}

test("every new screen opens cleanly", async ({ page }, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const csp = watchCsp(page);
  const email = await signUp(page, { business: `Corner Shop ${info.project.name}`, type: /Shop or tea stall/ });
  setPlan(email, "enterprise");

  await page.goto("/app/settings?tab=modules");
  for (const name of ["Inventory", "Accounting"]) {
    const toggle = page.getByRole("switch", { name, exact: true });
    await toggle.click();
    await expect(toggle).toBeChecked();
  }

  await opens(page, "/app/pos", "Sell");
  await opens(page, "/app/sales", "Sales");
  await opens(page, "/app/customers", "Customers and dues");
  await opens(page, "/app/expenses", "Expenses");
  await opens(page, "/app/inventory", "Stock");
  await expectAccessible(page, "inventory");
  await opens(page, "/app/accounting", "Accounts");
  await expectAccessible(page, "accounting");
  await opens(page, "/app/automations", "Automations");
  await opens(page, "/app/help", "Help");
  await page.getByLabel("Search help").fill("passkey");
  await expect(page.getByRole("heading", { name: "Keeping your account safe" })).toBeVisible();
  await expectAccessible(page, "help");

  await page.goto("/app/settings?tab=developers");
  await expect(page.getByRole("heading", { name: "API keys" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Webhooks" })).toBeVisible();
  await expectAccessible(page, "developers");
  await page.goto("/app/settings?tab=security");
  await expect(page.getByRole("heading", { name: "Company sign-in" })).toBeVisible();
  await expect(page.getByText("Redirect address to give your provider")).toBeVisible();
  await expectAccessible(page, "security");

  await page.goto("/app/account");
  await expect(page.getByRole("heading", { name: "Passkeys" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Till PIN" })).toBeVisible();

  expect(errors).toEqual([]);
  expect(csp).toEqual([]);
});

test("an API key is made once and shown once", async ({ page }, info) => {
  const email = await signUp(page, { business: `Keys Ltd ${info.project.name}` });
  setPlan(email, "business");
  await page.goto("/app/settings?tab=developers");
  await page.getByRole("button", { name: "New API key" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Name", { exact: true }).fill("Payroll export");
  await dialog.getByRole("checkbox").first().check();
  await dialog.getByRole("button", { name: "Make key" }).click();
  await expect(page.getByTestId("api-key-token")).toContainText("cmk_");
  await page.getByRole("button", { name: "Done" }).click();
  await expect(page.getByText("Payroll export")).toBeVisible();
  await expect(page.getByText(/never used/)).toBeVisible();
});

test("public legal and security pages", async ({ page }) => {
  const csp = watchCsp(page);
  for (const [path, heading] of [
    ["/terms", "Terms of Service"],
    ["/privacy", "Privacy Policy"],
    ["/dpa", "Data Processing Addendum"],
    ["/subprocessors", "Sub-processors"],
    ["/security", "Security"],
  ] as const) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
    await expectAccessible(page, path);
  }
  const txt = await page.request.get("/.well-known/security.txt");
  expect(await txt.text()).toContain("Contact: mailto:security@companymgmt.app");
  expect(csp).toEqual([]);
});

test("a device that isn't a till says so", async ({ page }) => {
  await page.goto("/till");
  await expect(page.getByRole("heading", { name: "This device isn't a till" })).toBeVisible();
});
