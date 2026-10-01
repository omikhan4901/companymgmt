import { expect, test } from "@playwright/test";

import { expectAccessible, signUp, watchCsp } from "./helpers";

test("an owner exports, deletes and restores the workspace", async ({ page }, info) => {
  const csp = watchCsp(page);
  const name = `Data Ltd ${info.project.name}`;
  await signUp(page, { business: name });

  await page.goto("/app/settings?tab=data");
  await expect(page.getByText("Export everything")).toBeVisible();
  await expectAccessible(page, "settings: data and security");
  const zip = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download export" }).click();
  expect((await zip).suggestedFilename()).toMatch(/-export-\d{8}\.zip$/);

  await page.goto("/app/account");
  const mine = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download my data" }).click();
  expect((await mine).suggestedFilename()).toMatch(/^my-data-\d{8}\.json$/);

  // Delete: the name has to be typed again.
  await page.goto("/app/settings?tab=data");
  await page.getByRole("button", { name: "Delete workspace…" }).click();
  const dialog = page.getByRole("dialog");
  const confirm = dialog.getByRole("button", { name: "Delete workspace" });
  await expect(confirm).toBeDisabled();
  await dialog.getByLabel(`Type ${name} to confirm`).fill(name);
  await expectAccessible(page, "delete dialog");
  await confirm.click();

  // The workspace is gone from the app; the owner can bring it back for 30 days.
  await expect(page).toHaveURL(/\/app\/account/);
  await expect(page.getByText(`${name} is scheduled for deletion`)).toBeVisible();
  await expectAccessible(page, "account: pending deletion");
  await page.getByRole("button", { name: "Restore workspace" }).click();
  await expect(page.getByText("Restored. Welcome back.")).toBeVisible();
  await page.goto("/app");
  await expect(page.getByRole("heading", { name: /Hi Rahim/ })).toBeVisible();
  expect(csp).toEqual([]);
});
