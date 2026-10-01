import { expect, test, type Browser } from "@playwright/test";

import { addStaff, expectAccessible, PASSWORD, signUp, watchCsp } from "./helpers";

/** A working day about two weeks ahead in Dhaka (Friday is the default day off). */
function workingDayAhead(days = 14): string {
  const dhaka = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Dhaka" }).format(new Date());
  const day = new Date(`${dhaka}T00:00:00Z`);
  day.setUTCDate(day.getUTCDate() + days);
  if (day.getUTCDay() === 5) day.setUTCDate(day.getUTCDate() + 1);
  return day.toISOString().slice(0, 10);
}

async function staffSignIn(browser: Browser, code: string, username: string, temp: string) {
  const context = await browser.newContext({ baseURL: "http://localhost:3000", locale: "en-GB", timezoneId: "Asia/Dhaka" });
  const staff = await context.newPage();
  await staff.goto("/login");
  await staff.getByText("Staff sign-in (no email)").click();
  await staff.getByLabel("Workspace code").fill(code);
  await staff.getByLabel("Username").fill(username);
  await staff.getByLabel(/^Password$/).fill(temp);
  await staff.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(staff).toHaveURL(/change-password/);
  await staff.getByLabel("Current password").fill(temp);
  await staff.getByLabel("New password").fill(PASSWORD);
  await staff.getByRole("button", { name: "Save" }).click();
  await expect(staff.getByRole("heading", { name: /Hi/ })).toBeVisible();
  return { context, staff };
}

test("staff ask for leave and the owner approves it", async ({ page, browser }, info) => {
  const csp = watchCsp(page);
  await signUp(page, { business: `Leave Ltd ${info.project.name}` });
  const username = `nadia${Date.now() % 100000}`;
  const { code, temp } = await addStaff(page, "Nadia Islam", username);

  const { context, staff } = await staffSignIn(browser, code, username, temp);
  const staffCsp = watchCsp(staff);
  await staff.goto("/app/leave");
  await expect(staff.getByRole("heading", { name: "Leave", level: 1 })).toBeVisible();
  await expect(staff.getByText("Casual leave").first()).toBeVisible();
  await expectAccessible(staff, "leave: mine");

  const day = workingDayAhead();
  await staff.getByRole("button", { name: "Ask for leave" }).click();
  const dialog = staff.getByRole("dialog");
  await dialog.getByLabel("Type").selectOption({ label: "Casual leave" });
  await dialog.getByLabel("From").fill(day);
  await dialog.getByLabel("To").fill(day);
  await dialog.getByLabel(/^Reason/).fill("Family wedding");
  await expect(dialog.getByText("1 day", { exact: true })).toBeVisible();
  await expect(dialog.getByText("9 left after this")).toBeVisible();
  await expectAccessible(staff, "leave: ask dialog");
  await dialog.getByRole("button", { name: "Ask for leave" }).click();
  await expect(staff.getByText("Request sent.")).toBeVisible();
  await expect(staff.getByText("Waiting", { exact: true }).first()).toBeVisible();

  // Staff see the calendar but not other people's balances or the settings.
  await staff.goto("/app/leave?tab=calendar");
  await expect(staff.getByRole("tab", { name: "Balances" })).toHaveCount(0);
  await expect(staff.getByRole("tab", { name: "Settings" })).toHaveCount(0);
  await expectAccessible(staff, "leave: calendar (staff)");

  // The owner approves it from the requests tab.
  await page.goto("/app/leave?tab=requests");
  const card = page.getByRole("listitem").filter({ hasText: "Nadia Islam" });
  await expect(card.getByText("Family wedding")).toBeVisible();
  await expectAccessible(page, "leave: requests");
  await card.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText("Approved.")).toBeVisible();

  await page.goto(`/app/leave?tab=calendar`);
  await page.getByLabel("Month").fill(day.slice(0, 7));
  await expect(page.getByRole("rowheader", { name: "Nadia Islam" })).toBeVisible();
  await expectAccessible(page, "leave: calendar");
  await page.goto("/app/leave?tab=balances");
  await expect(page.getByRole("cell", { name: "Nadia Islam", exact: true })).toBeVisible();
  await expectAccessible(page, "leave: balances");
  await page.goto("/app/leave?tab=settings");
  await expect(page.getByText("Earned leave")).toBeVisible();
  await expectAccessible(page, "leave: settings");
  await page.getByRole("button", { name: "Edit: Casual leave" }).click();
  await expectAccessible(page, "leave: type dialog");
  await page.getByRole("dialog").getByRole("button", { name: "Cancel" }).click();

  // Back on the staff phone: approved, and the balance went down.
  await staff.goto("/app/leave");
  await expect(staff.getByText("Approved", { exact: true }).first()).toBeVisible();
  await expect(staff.getByText("Used 1")).toBeVisible();
  expect(staffCsp).toEqual([]);
  await context.close();
  expect(csp).toEqual([]);
});
