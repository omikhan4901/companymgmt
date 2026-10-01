import { expect, test } from "@playwright/test";

import { addStaff, expectAccessible, signUp, staffSignIn, watchCsp } from "./helpers";

const PDF = Buffer.from("%PDF-1.7\n% Code of conduct\n");

test("a checklist starts for a new joiner and reading the policy ticks it off", async ({ page, browser }, info) => {
  const csp = watchCsp(page);
  await signUp(page, { business: `Onboard Ltd ${info.project.name}` });

  // A policy to read in the first week.
  await page.goto("/app/documents");
  await page.getByRole("button", { name: "New document" }).click();
  const docDialog = page.getByRole("dialog");
  await docDialog.getByLabel("Title").fill("Code of conduct");
  await docDialog.getByLabel("File").setInputFiles({ name: "code-of-conduct.pdf", mimeType: "application/pdf", buffer: PDF });
  await docDialog.getByRole("switch", { name: "Ask people to acknowledge it" }).click();
  await docDialog.getByRole("button", { name: "Publish" }).click();
  await page.getByRole("dialog", { name: "Code of conduct" }).getByRole("button", { name: "Close" }).click();

  // The checklist, started by itself for everyone who joins.
  await page.goto("/app/tasks?tab=onboarding");
  await expect(page.getByText("No checklists yet")).toBeVisible();
  await expectAccessible(page, "onboarding: empty");
  await page.getByRole("button", { name: "New checklist" }).click();
  const dialog = page.getByRole("dialog", { name: "New checklist" });
  await dialog.getByLabel("Name", { exact: true }).fill("First week");
  await dialog.getByRole("switch", { name: "Start it for everyone who joins" }).click();
  await dialog.getByLabel("Item 1", { exact: true }).fill("Read the code of conduct");
  await dialog.getByLabel("Document to read").selectOption({ label: "Code of conduct" });
  await dialog.getByRole("button", { name: "Add an item" }).click();
  await dialog.getByLabel("Item 2", { exact: true }).fill("Set up their laptop");
  await dialog.getByLabel("Who does it").nth(1).selectOption({ label: "Their manager" });
  await dialog.getByLabel("Days after starting").nth(1).fill("1");
  await expectAccessible(page, "onboarding: checklist editor");
  await dialog.getByRole("button", { name: "Save" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByText("First week")).toBeVisible();
  await expect(page.getByText("Starts by itself")).toBeVisible();

  const username = `rina${Date.now() % 100000}`;
  const { code, temp } = await addStaff(page, "Rina Akter", username);
  await page.goto("/app/tasks?tab=onboarding");
  await expect(page.getByText("Rina Akter")).toBeVisible();
  await expect(page.getByText("0 of 2 done")).toBeVisible();
  await expectAccessible(page, "onboarding: in progress");

  // Rina sees her first days, opens the policy from her task and acknowledges it.
  const { context, staff } = await staffSignIn(browser, code, username, temp);
  await expect(staff.getByText("Your first days")).toBeVisible();
  await staff.goto("/app/tasks");
  await staff.getByRole("button", { name: /^Read the code of conduct/ }).click();
  const sheet = staff.getByRole("dialog", { name: /Read the code of conduct/ });
  await expect(sheet.getByText("Acknowledging it ticks this off.")).toBeVisible();
  await expectAccessible(staff, "onboarding: joiner's task");
  await sheet.getByRole("link", { name: /Open the document/ }).click();
  const doc = staff.getByRole("dialog", { name: "Code of conduct" });
  await doc.getByRole("button", { name: "I've read and understood it" }).click();
  await expect(doc.getByText("You've acknowledged this version.")).toBeVisible();
  await staff.goto("/app");
  await expect(staff.getByText("1 of 2 done")).toBeVisible();
  await context.close();

  // The manager's item is theirs, and the list shows the progress.
  await page.goto("/app/tasks");
  await expect(page.getByRole("button", { name: /^Set up their laptop/ })).toBeVisible();
  await page.goto("/app/tasks?tab=onboarding");
  await expect(page.getByText("1 of 2 done")).toBeVisible();

  // Starting one by hand.
  await page.getByRole("button", { name: "Start onboarding" }).click();
  const start = page.getByRole("dialog", { name: "Start onboarding" });
  await start.getByLabel("Person").selectOption({ label: "Rahim Uddin" });
  await expectAccessible(page, "onboarding: start");
  await start.getByRole("button", { name: "Start", exact: true }).click();
  await expect(page.getByText("Onboarding started for Rahim Uddin.")).toBeVisible();
  await expect(page.getByText("Rahim Uddin", { exact: true })).toBeVisible();
  expect(csp).toEqual([]);
});
