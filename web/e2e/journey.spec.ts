import { expect, test } from "@playwright/test";

import { expectAccessible, PASSWORD, signUp } from "./helpers";

test("an owner signs up, adds a staff member, and both see attendance", async ({ page, browser }, info) => {
  const email = await signUp(page, { business: `Cha Ghor ${info.project.name}` });
  await expect(page.getByRole("heading", { name: /Hi Rahim/ })).toBeVisible();
  await expectAccessible(page, "home");

  // Owner clocks in from the home screen.
  await page.getByRole("button", { name: "Clock in" }).click();
  await expect(page.getByText(/Clocked in since/)).toBeVisible();

  // Add a staff member without email.
  await page.goto("/team");
  await expect(page.getByRole("heading", { name: "Team" })).toBeVisible();
  await expectAccessible(page, "team");
  await page.getByRole("button", { name: "Add staff without email" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Name", { exact: true }).fill("করিম মিয়া");
  const username = `karim${Date.now() % 100000}`;
  await dialog.getByLabel("Username", { exact: true }).fill(username);
  await dialog.getByRole("button", { name: "Add" }).click();
  await expect(dialog.getByText("Staff account created")).toBeVisible();
  const secret = async (id: string) => (await page.getByTestId(id).locator(".ant-typography").innerText()).trim();
  const code = await secret("workspace-code");
  const temp = await secret("temporary-password");
  await dialog.getByRole("button", { name: "Close" }).first().click();

  // The staff member signs in on their own phone and must choose a password.
  const staffContext = await browser.newContext({ baseURL: "http://localhost:5173", locale: "bn-BD", timezoneId: "Asia/Dhaka" });
  const staff = await staffContext.newPage();
  await staff.goto("/login");
  await staff.getByText(/কর্মী সাইন-ইন|Staff sign-in/).click();
  await staff.getByLabel(/ওয়ার্কস্পেস কোড|Workspace code/).fill(code);
  await staff.getByLabel(/ইউজারনেম|Username/).fill(username);
  await staff.getByLabel(/^(পাসওয়ার্ড|Password)$/).fill(temp);
  await staff.getByRole("button", { name: /সাইন ইন|Sign in/ }).click();
  await expect(staff).toHaveURL(/change-password/);
  await staff.getByLabel(/বর্তমান পাসওয়ার্ড|Current password/).fill(temp);
  await staff.getByLabel(/নতুন পাসওয়ার্ড|New password/).fill(PASSWORD);
  await staff.getByRole("button", { name: /সংরক্ষণ|Save/ }).click();
  await expect(staff.getByRole("heading", { name: /হ্যালো|Hi/ })).toBeVisible();
  await expectAccessible(staff, "staff home (Bangla)");
  await staff.getByRole("button", { name: /হাজিরা দিন|Clock in/ }).click();
  await expect(staff.getByText(/থেকে কাজে আছেন|Clocked in since/)).toBeVisible();
  // Staff can't see the team page.
  await expect(staff.getByRole("link", { name: /টিম|Team/ })).toHaveCount(0);
  await staffContext.close();

  // The owner sees both people at work and the timesheet.
  await page.goto("/attendance?tab=today");
  await expect(page.getByText("করিম মিয়া").first()).toBeVisible();
  await expectAccessible(page, "attendance today");
  await page.goto("/attendance?tab=timesheet");
  await expect(page.getByRole("cell", { name: "করিম মিয়া" })).toBeVisible();

  // People and settings pages render and pass accessibility checks.
  for (const path of ["/people", "/people?tab=departments", "/settings", "/settings?tab=plan", "/settings?tab=audit", "/account"]) {
    await page.goto(path);
    await expect(page.locator("main h1")).toBeVisible();
    await expectAccessible(page, path);
  }
  expect(email).toContain("@");
});

test("sign-in pages are accessible in both languages", async ({ page }) => {
  for (const path of ["/login", "/signup", "/forgot-password"]) {
    await page.goto(path);
    await expectAccessible(page, `${path} en`);
  }
  await page.goto("/login");
  await page.getByRole("button", { name: "বাংলা" }).click();
  await expect(page.getByRole("heading", { name: "আবার স্বাগতম" })).toBeVisible();
  await expectAccessible(page, "/login bn");
});

test("wrong password shows one clear message", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("textbox", { name: "Email" }).fill("nobody@example.com");
  await page.getByLabel("Password", { exact: true }).fill("not the right one");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("The sign-in details are incorrect.")).toBeVisible();
});
