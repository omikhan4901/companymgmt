import { expect, test } from "@playwright/test";

import { expectAccessible, signUp, watchCsp } from "./helpers";

const csv = (text: string) => ({ name: "team.csv", mimeType: "text/csv", buffer: Buffer.from(text) });

const BROKEN = [
  "Name,Code,Email,Department,Joined on,Casual leave (days left)",
  "Nusrat Jahan,E-1,nusrat@example.com,Design / Motion,15/01/2024,7.5",
  "Fahim Shahriar,E-1,fahim-at-example,Design,31/02/2024,10",
  "সুমাইয়া ইসলাম,E-3,,Sales,,",
].join("\n");
const FIXED = BROKEN.replace("Fahim Shahriar,E-1,fahim-at-example,Design,31/02/2024", "Fahim Shahriar,E-2,fahim@example.com,Design,29/02/2024");

test("an owner imports the team from a spreadsheet, fixing the file first", async ({ page }, info) => {
  const csp = watchCsp(page);
  await signUp(page, { business: `Import Ltd ${info.project.name}` });
  await page.goto("/app/people");
  await page.getByRole("button", { name: "Import" }).click();
  const dialog = page.getByRole("dialog", { name: "Import people from a spreadsheet" });

  const downloading = page.waitForEvent("download");
  await dialog.getByRole("button", { name: "Download the template" }).click();
  expect((await downloading).suggestedFilename()).toBe("people-import.csv");

  // A file with mistakes: every problem is listed, and nothing can be imported yet.
  await dialog.getByLabel("CSV file").setInputFiles(csv(BROKEN));
  await expect(dialog.getByText("1 row with problems")).toBeVisible();
  const problems = dialog.getByRole("region", { name: "Rows with problems" });
  await expect(problems.getByText("Line 2 has the same code.")).toBeVisible();
  await expect(problems.getByText("This doesn't look like an email address.")).toBeVisible();
  await expect(problems.getByText("Write the date like 2024-01-15 or 15/01/2024.")).toBeVisible();
  await expect(dialog.getByRole("button", { name: /^Import \d+ people$/ })).toBeDisabled();
  await expectAccessible(page, "import: problems");

  // Fixed: three new people and three new departments, then imported.
  await dialog.getByLabel("CSV file").setInputFiles(csv(FIXED));
  await expect(dialog.getByText("3 new people")).toBeVisible();
  await expect(dialog.getByText("Everything checks out.", { exact: false })).toBeVisible();
  await expect(dialog.getByText("Design, Design / Motion, Sales")).toBeVisible();
  await expectAccessible(page, "import: ready");
  await dialog.getByRole("button", { name: "Import 3 people" }).click();
  await expect(page.getByText("Imported: 3 added, 0 updated.")).toBeVisible();
  await expect(dialog).toHaveCount(0);
  for (const name of ["Nusrat Jahan", "Fahim Shahriar", "সুমাইয়া ইসলাম"]) {
    await expect(page.getByText(name, { exact: true }).first()).toBeVisible();
  }

  // The same file again changes nothing.
  await page.getByRole("button", { name: "Import" }).click();
  await page.getByRole("dialog").getByLabel("CSV file").setInputFiles(csv(FIXED));
  await expect(page.getByRole("dialog").getByText("3 already up to date")).toBeVisible();
  expect(csp).toEqual([]);
});
