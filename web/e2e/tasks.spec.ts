import { expect, test } from "@playwright/test";

import { addStaff, expectAccessible, signUp, staffSignIn, watchCsp } from "./helpers";

test("a manager plans a project and staff work through their tasks", async ({ page, browser }, info) => {
  const csp = watchCsp(page);
  await signUp(page, { business: `Pixel Agency ${info.project.name}` });
  const username = `nadia${Date.now() % 100000}`;
  const { code, temp } = await addStaff(page, "Nadia Islam", username);

  // An empty start explains what projects are for.
  await page.goto("/app/tasks?tab=projects");
  await expect(page.getByRole("heading", { name: "Tasks", level: 1 })).toBeVisible();
  await expect(page.getByText("No projects yet")).toBeVisible();
  await expectAccessible(page, "tasks: no projects");

  await page.getByRole("button", { name: "New project" }).first().click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Name", { exact: true }).fill("Website relaunch");
  await dialog.getByRole("checkbox", { name: "Nadia Islam" }).check();
  await dialog.getByRole("button", { name: "Teal" }).click();
  await expectAccessible(page, "tasks: project dialog");
  await dialog.getByRole("button", { name: "Create project" }).click();

  // Straight onto the board; add a card to To do.
  await expect(page.getByRole("heading", { name: "Website relaunch" })).toBeVisible();
  const todo = page.getByRole("region", { name: "To do" });
  await todo.getByRole("button", { name: "Add a task" }).click();
  await todo.getByLabel("New task in To do").fill("Homepage copy");
  await todo.getByRole("button", { name: "Add", exact: true }).click();
  await expect(todo.getByRole("button", { name: /^Homepage copy/ })).toBeVisible();
  await expectAccessible(page, "tasks: board");

  // Open it: give it to Nadia, add a checklist item and a comment.
  await todo.getByRole("button", { name: /^Homepage copy/ }).click();
  const sheet = page.getByRole("dialog", { name: "Homepage copy" });
  await sheet.getByLabel("Assigned to").selectOption({ label: "Nadia Islam" });
  await expect(page.getByText("Nadia Islam").first()).toBeVisible();
  await sheet.getByLabel("Add an item").fill("Write the hero line");
  await sheet.getByRole("button", { name: "Add", exact: true }).click();
  await expect(sheet.getByRole("checkbox", { name: "Write the hero line" })).toBeVisible();
  await sheet.getByLabel("Write a comment").fill("Keep it short, please.");
  await sheet.getByRole("button", { name: "Send comment" }).click();
  await expect(sheet.getByText("Keep it short, please.")).toBeVisible();
  await expectAccessible(page, "tasks: task sheet");
  await sheet.getByRole("button", { name: "Close" }).click();

  // Move it to Doing from the card's menu (the keyboard way).
  await page.getByRole("button", { name: "Move “Homepage copy”" }).click();
  await page.getByRole("menuitem", { name: "Doing" }).click();
  await expect(page.getByRole("region", { name: "Doing" }).getByRole("button", { name: /^Homepage copy/ })).toBeVisible();

  // Nadia hears about it, finds it under My work, and finishes it.
  const { context, staff } = await staffSignIn(browser, code, username, temp);
  await staff.getByRole("button", { name: /Notifications, \d+ unread/ }).click();
  await expect(staff.getByText(/gave you a task: Homepage copy/)).toBeVisible();
  await staff.keyboard.press("Escape");
  await staff.goto("/app/tasks");
  await expect(staff.getByRole("heading", { name: "Tasks", level: 1 })).toBeVisible();
  await expect(staff.getByRole("button", { name: "New project" })).toHaveCount(0);
  await staff.getByRole("button", { name: /^Homepage copy/ }).click();
  const mine = staff.getByRole("dialog", { name: "Homepage copy" });
  await mine.getByRole("checkbox", { name: "Write the hero line" }).check();
  await mine.getByLabel("Status").selectOption({ label: "Done" });
  await expect(mine.getByLabel("Status")).toHaveValue("done");
  await expectAccessible(staff, "tasks: staff sheet");
  await context.close();

  // The owner is told it's done.
  await page.goto("/app");
  await page.getByRole("button", { name: /Notifications, \d+ unread/ }).click();
  await expect(page.getByText(/Nadia Islam finished Homepage copy/)).toBeVisible();
  expect(csp).toEqual([]);
});
