import { expect, test } from "@playwright/test";

import { addStaff, expectAccessible, signUp, staffSignIn, watchCsp } from "./helpers";

/** A working day about two weeks ahead in Dhaka (Friday is the default day off). */
function workingDayAhead(days = 15): string {
  const dhaka = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Dhaka" }).format(new Date());
  const day = new Date(`${dhaka}T00:00:00Z`);
  day.setUTCDate(day.getUTCDate() + days);
  if (day.getUTCDay() === 5) day.setUTCDate(day.getUTCDate() + 1);
  return day.toISOString().slice(0, 10);
}

test("a manager decides leave and a time fix from one inbox", async ({ page, browser }, info) => {
  const csp = watchCsp(page);
  await signUp(page, { business: `Inbox Ltd ${info.project.name}` });
  const username = `karim${Date.now() % 100000}`;
  const { code, temp } = await addStaff(page, "Karim Hossain", username);

  // Karim asks for a day off and for a missed shift to be added.
  const { context, staff } = await staffSignIn(browser, code, username, temp);
  await staff.goto("/app/leave");
  await staff.getByRole("button", { name: "Ask for leave" }).click();
  const ask = staff.getByRole("dialog");
  const day = workingDayAhead();
  await ask.getByLabel("From").fill(day);
  await ask.getByLabel("To").fill(day);
  await ask.getByRole("button", { name: "Ask for leave" }).click();
  await expect(staff.getByText("Request sent.")).toBeVisible();
  await staff.goto("/app/attendance");
  await staff.getByRole("button", { name: "Add a missing shift" }).click();
  const fix = staff.getByRole("dialog");
  const shift = workingDayAhead(-2);
  await fix.getByLabel("Start").fill(`${shift}T09:00`);
  await fix.getByLabel("End").fill(`${shift}T17:00`);
  await fix.getByLabel(/^Reason/).fill("Phone was dead");
  await fix.getByRole("button", { name: "Ask to fix" }).click();
  await expect(staff.getByText("Request sent.")).toBeVisible();

  // The owner finds both in the inbox, oldest first.
  await page.goto("/app/approvals");
  await expect(page.getByRole("heading", { name: "Approvals", level: 1 })).toBeVisible();
  await expect(page.getByRole("tab", { name: "All (2)" })).toBeVisible();
  await expectAccessible(page, "approvals: inbox");
  await page.getByLabel("Note (optional): Karim Hossain").first().fill("Enjoy the day");
  await page.getByRole("button", { name: "Approve: Karim Hossain" }).first().click();
  await expect(page.getByText("Approved for Karim Hossain.")).toBeVisible();
  await page.getByRole("tab", { name: "Time fixes (1)" }).click();
  await page.getByRole("button", { name: "Reject: Karim Hossain" }).click();
  await expect(page.getByText("Nothing waiting for you")).toBeVisible();
  await expectAccessible(page, "approvals: empty");

  // Karim hears both decisions.
  await staff.goto("/app");
  await staff.getByRole("button", { name: /Notifications, 2 unread/ }).click();
  await expect(staff.getByText(/approved your Casual leave/)).toBeVisible();
  await expect(staff.getByText(/turned down your time fix/)).toBeVisible();
  await context.close();
  expect(csp).toEqual([]);
});
