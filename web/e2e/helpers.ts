import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

export const PASSWORD = "a long and happy passphrase";
export const SHOP = { latitude: 23.7386, longitude: 90.3958, accuracy: 15 };

export function uniqueEmail(prefix = "owner"): string {
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
}

/** WCAG 2.2 AA checks on the current page (serious and critical findings fail), plus no sideways scrolling. */
export async function expectAccessible(page: Page, label: string): Promise<void> {
  const [scroll, client] = await page.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]);
  expect(scroll, `${label}: page is wider than the screen`).toBeLessThanOrEqual(client);
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
  const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(serious.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(", ")}`), label).toEqual([]);
}

/** Fails the test if the page breaks its own Content Security Policy. */
export function watchCsp(page: Page): string[] {
  const violations: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error" && /Content Security Policy/i.test(m.text())) violations.push(m.text());
  });
  return violations;
}

export async function signUp(page: Page, opts: { name?: string; business?: string; email?: string } = {}) {
  const email = opts.email ?? uniqueEmail();
  await page.goto("/signup");
  await page.getByRole("button", { name: "English" }).click();
  await page.getByLabel("Your name").fill(opts.name ?? "Rahim Uddin");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByLabel("Business name").fill(opts.business ?? "Cha Ghor");
  await page.getByRole("radio", { name: /Office or services/ }).click();
  await page.getByRole("button", { name: "Create workspace" }).click();
  await expect(page).toHaveURL(/\/app$/);
  return email;
}

export async function signIn(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/app$/);
}

/** Adds a staff account on the Team page and returns its sign-in details. */
export async function addStaff(page: Page, name: string, username: string) {
  await page.goto("/app/team");
  await page.getByRole("button", { name: "Add staff without email" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Name", { exact: true }).fill(name);
  await dialog.getByLabel("Username", { exact: true }).fill(username);
  await dialog.getByRole("button", { name: "Add", exact: true }).click();
  await expect(dialog.getByText("Staff account created")).toBeVisible();
  const code = (await dialog.getByTestId("workspace-code").locator("code").innerText()).trim();
  const temp = (await dialog.getByTestId("temporary-password").locator("code").innerText()).trim();
  await dialog.getByRole("button", { name: "Done" }).click();
  return { code, temp };
}
