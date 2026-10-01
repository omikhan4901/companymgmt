import { expect, test } from "@playwright/test";

import { addStaff, expectAccessible, signUp, staffSignIn, watchCsp } from "./helpers";

test("an owner posts news, staff are told and read it, and the owner sees who has", async ({ page, browser }, info) => {
  const csp = watchCsp(page);
  await signUp(page, { business: `News Ltd ${info.project.name}` });
  const username = `nadia${Date.now() % 100000}`;
  const { code, temp } = await addStaff(page, "Nadia Islam", username);

  await page.goto("/app/announcements");
  await expect(page.getByRole("heading", { name: "Announcements", level: 1 })).toBeVisible();
  await expect(page.getByText("No announcements yet")).toBeVisible();
  await expectAccessible(page, "news: empty");

  await page.getByRole("button", { name: "New post" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Title").fill("Office closed for Eid");
  await dialog.getByLabel("Message").fill("We're closed from Monday to Wednesday. Eid Mubarak!");
  await dialog.getByRole("switch", { name: "Pin to the top" }).click();
  await expectAccessible(page, "news: new post");
  await dialog.getByRole("button", { name: "Publish" }).click();
  await expect(page.getByRole("heading", { name: /Office closed for Eid/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Read by 1 of 2" })).toBeVisible();
  await expectAccessible(page, "news: feed");

  // Nadia is told, opens it, and it counts as read.
  const { context, staff } = await staffSignIn(browser, code, username, temp);
  await expect(staff.getByText("Latest news")).toBeVisible();
  await staff.getByRole("button", { name: /Notifications, \d+ unread/ }).click();
  await staff.getByRole("button", { name: /posted: Office closed for Eid/ }).click();
  await expect(staff).toHaveURL(/\/app\/announcements\?post=/);
  await expect(staff.getByText("Eid Mubarak!", { exact: false })).toBeVisible();
  await expect(staff.getByRole("button", { name: "New post" })).toHaveCount(0);
  await expectAccessible(staff, "news: staff feed");
  await context.close();

  await page.reload();
  await page.getByRole("button", { name: "Read by 2 of 2" }).click();
  const receipts = page.getByRole("dialog", { name: "Who has read it" });
  await expect(receipts.getByText("Nadia Islam")).toBeVisible();
  await expectAccessible(page, "news: receipts");
  expect(csp).toEqual([]);
});
