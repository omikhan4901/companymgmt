import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

export const PASSWORD = "a long and happy passphrase";

export function uniqueEmail(prefix = "owner"): string {
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
}

/** WCAG 2.2 AA checks on the current page. */
export async function expectAccessible(page: Page, label: string): Promise<void> {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
  const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(serious.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(", ")}`), label).toEqual([]);
}

export async function signUp(page: Page, opts: { name?: string; business?: string; email?: string; language?: "English" | "বাংলা" } = {}) {
  const email = opts.email ?? uniqueEmail();
  await page.goto("/signup");
  await page.getByRole("button", { name: opts.language ?? "English" }).click();
  await page.getByLabel(/Your name|আপনার নাম/).fill(opts.name ?? "Rahim Uddin");
  await page.getByLabel(/^Email$|^ইমেইল$/).fill(email);
  await page.getByLabel(/^Password$|^পাসওয়ার্ড$/).fill(PASSWORD);
  await page.getByRole("button", { name: /Next|পরবর্তী/ }).click();
  await page.getByLabel(/Business name|ব্যবসার নাম/).fill(opts.business ?? "Cha Ghor");
  await page.getByRole("radio", { name: /Office or services|অফিস বা সেবা/ }).click();
  await page.getByRole("button", { name: /Create workspace|ওয়ার্কস্পেস তৈরি করুন/ }).click();
  await expect(page).toHaveURL(/\/$/);
  return email;
}
