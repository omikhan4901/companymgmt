import { expect, test } from "@playwright/test";

import { addStaff, expectAccessible, PASSWORD, signUp, watchCsp } from "./helpers";

test("the owner runs payroll and staff download their payslip", async ({ page, browser }, info) => {
  const csp = watchCsp(page);
  await signUp(page, { business: `Pay Ltd ${info.project.name}` });
  const username = `rafiq${Date.now() % 100000}`;
  const { code, temp } = await addStaff(page, "Rafiq Islam", username);

  // Set Rafiq's salary, paid to a bKash wallet.
  await page.goto("/app/payroll?tab=salaries");
  await expect(page.getByRole("heading", { name: "Payroll", level: 1 })).toBeVisible();
  await expectAccessible(page, "payroll: salaries (empty)");
  await page.getByRole("button", { name: "Set salary" }).click();
  const salary = page.getByRole("dialog");
  await salary.getByLabel("Person").selectOption({ label: "Rafiq Islam" });
  await salary.getByLabel("From").fill("2024-01-01");
  await salary.getByLabel("Basic").fill("20,800");
  await salary.getByLabel("House rent").fill("10400");
  await salary.getByLabel("Medical").fill("1500");
  await expect(salary.getByText("32,700")).toBeVisible();
  await salary.getByLabel("Paid by").selectOption("wallet");
  await salary.getByLabel("Bank or wallet").fill("bKash");
  await salary.getByLabel("Account number").fill("01712345678");
  await expectAccessible(page, "payroll: salary dialog");
  await salary.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("cell", { name: "Rafiq Islam", exact: true })).toBeVisible();
  await expect(page.getByText("··5678")).toBeVisible();
  await expectAccessible(page, "payroll: salaries");

  // Run last month's payroll, send it for approval and finalize it.
  await page.getByRole("tab", { name: "Pay runs" }).click();
  await page.getByRole("button", { name: "Run payroll" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Run payroll" }).click();
  await expect(page.getByText("Draft", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Rafiq Islam" })).toBeVisible();
  await expectAccessible(page, "payroll: draft run");
  await page.getByRole("button", { name: "Send for approval" }).click();
  await expect(page.getByText("Waiting for approval", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Finalize" }).click();
  await expectAccessible(page, "payroll: finalize dialog");
  await page.getByRole("dialog").getByRole("button", { name: "Finalize" }).click();
  await expect(page.getByText("Finalized. People can see their payslips now.")).toBeVisible();
  const sheet = page.waitForEvent("download");
  await page.getByRole("button", { name: "Transfer sheet (CSV)" }).click();
  expect((await sheet).suggestedFilename()).toMatch(/payroll-\d{4}-\d{2}-transfers\.csv/);
  await page.getByRole("button", { name: "Rafiq Islam" }).click();
  await expect(page.getByRole("dialog").getByText("Net pay")).toBeVisible();
  await expectAccessible(page, "payroll: payslip dialog");
  await page.getByRole("dialog").getByRole("button", { name: "Close" }).first().click();

  for (const tab of ["advances", "settings"]) {
    await page.goto(`/app/payroll?tab=${tab}`);
    await expect(page.locator("main h1")).toBeVisible();
    await expectAccessible(page, `payroll: ${tab}`);
  }
  expect(csp).toEqual([]);

  // Rafiq signs in and downloads the payslip.
  const context = await browser.newContext({ baseURL: "http://localhost:3000", locale: "en-GB", timezoneId: "Asia/Dhaka" });
  const staff = await context.newPage();
  await staff.goto("/login");
  await staff.getByText("Staff sign-in (no email)").click();
  await staff.getByLabel("Workspace code").fill(code);
  await staff.getByLabel("Username").fill(username);
  await staff.getByLabel(/^Password$/).fill(temp);
  await staff.getByRole("button", { name: "Sign in", exact: true }).click();
  await staff.getByLabel("Current password").fill(temp);
  await staff.getByLabel("New password").fill(PASSWORD);
  await staff.getByRole("button", { name: "Save" }).click();
  await expect(staff.getByRole("heading", { name: /Hi/ })).toBeVisible();
  await staff.goto("/app/payroll");
  await expect(staff.getByRole("tab", { name: "Salaries" })).toHaveCount(0);
  await expectAccessible(staff, "payroll: my payslips");
  await staff.getByText("Net pay").first().click();
  const pdf = staff.waitForEvent("download");
  await staff.getByRole("dialog").getByRole("button", { name: "বাংলায় PDF" }).click();
  expect((await pdf).suggestedFilename()).toMatch(/payslip-\d{4}-\d{2}-bn\.pdf/);
  await context.close();
});
