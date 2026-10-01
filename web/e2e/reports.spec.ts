import { expect, test } from "@playwright/test";

import { expectAccessible, signUp, watchCsp } from "./helpers";

test("an owner sets working hours and reads the reports", async ({ page }, info) => {
  const csp = watchCsp(page);
  await signUp(page, { business: `Reports Ltd ${info.project.name}` });

  await page.goto("/app/settings?tab=branches");
  await expect(page.getByRole("heading", { name: "Working hours" })).toBeVisible();
  await page.getByLabel("The working day starts at").fill("10:00");
  await page.getByLabel("The working day starts at").blur();
  await expect(page.getByText("Saved").first()).toBeVisible();
  await page.getByLabel("Late after").selectOption({ label: "30 minutes" });
  await expect(page.getByText("Saved")).toHaveCount(2);
  await page.reload();
  await expect(page.getByLabel("The working day starts at")).toHaveValue("10:00");
  await expect(page.getByLabel("Late after")).toHaveValue("30");

  await page.goto("/app/reports");
  await expect(page.getByRole("heading", { name: "Reports", level: 1 })).toBeVisible();
  await expect(page.getByText("0 joined · 0 left").locator("xpath=..").getByText("1", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Attendance by day" })).toBeVisible();
  await page.getByLabel("Period").selectOption({ label: "Last month" });
  await expect(page.getByText("Nobody took leave in this period.")).toBeVisible();
  await expectAccessible(page, "reports");
  expect(csp).toEqual([]);
});
