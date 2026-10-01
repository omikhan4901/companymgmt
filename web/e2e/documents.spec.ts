import { expect, test } from "@playwright/test";

import { addStaff, expectAccessible, signUp, staffSignIn, watchCsp } from "./helpers";

const PDF = Buffer.from("%PDF-1.7\n% Code of conduct\n");

test("an owner publishes a policy and staff read and acknowledge it", async ({ page, browser }, info) => {
  const csp = watchCsp(page);
  await signUp(page, { business: `Docs Ltd ${info.project.name}` });
  const username = `nadia${Date.now() % 100000}`;
  const { code, temp } = await addStaff(page, "Nadia Islam", username);

  await page.goto("/app/documents");
  await expect(page.getByRole("heading", { name: "Documents", level: 1 })).toBeVisible();
  await expect(page.getByText("No documents yet")).toBeVisible();
  await expectAccessible(page, "docs: empty");

  await page.getByRole("button", { name: "New document" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Title").fill("Code of conduct");
  await dialog.getByLabel("File").setInputFiles({ name: "code-of-conduct.pdf", mimeType: "application/pdf", buffer: PDF });
  await dialog.getByRole("switch", { name: "Ask people to acknowledge it" }).click();
  await expectAccessible(page, "docs: new document");
  await dialog.getByRole("button", { name: "Publish" }).click();
  const sheet = page.getByRole("dialog", { name: "Code of conduct" });
  await expect(sheet.getByText("Acknowledged by 0 of 2")).toBeVisible();
  await expectAccessible(page, "docs: document (manager)");
  await sheet.getByRole("button", { name: "Close" }).click();

  // Nadia sees it waiting for her, reads it and acknowledges it.
  const { context, staff } = await staffSignIn(browser, code, username, temp);
  await expect(staff.getByText("To read")).toBeVisible();
  await staff.goto("/app/documents");
  await expect(staff.getByText("1 document is waiting for you to read")).toBeVisible();
  await expect(staff.getByRole("button", { name: "New document" })).toHaveCount(0);
  await staff.getByRole("button", { name: /^Code of conduct/ }).first().click();
  const mine = staff.getByRole("dialog", { name: "Code of conduct" });
  const downloading = staff.waitForEvent("download");
  await mine.getByRole("button", { name: "Download code-of-conduct.pdf", exact: true }).click();
  expect((await downloading).suggestedFilename()).toBe("code-of-conduct.pdf");
  await expectAccessible(staff, "docs: document (staff)");
  await mine.getByRole("button", { name: "I've read and understood it" }).click();
  await expect(mine.getByText("You've acknowledged this version.")).toBeVisible();
  await context.close();

  await page.reload();
  await page.getByRole("button", { name: /^Code of conduct/ }).first().click();
  await expect(page.getByRole("dialog", { name: "Code of conduct" }).getByText("Acknowledged by 1 of 2")).toBeVisible();
  expect(csp).toEqual([]);
});
