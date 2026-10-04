import { expect, test } from "@playwright/test";

import { addStaff, expectAccessible, signUp, staffSignIn, watchCsp } from "./helpers";

// The API runs with AI_PROVIDER=fake: a scripted model that looks things up with the
// same tools, and answers by quoting them. No real AI service is called.
test("an owner switches the assistant on and people ask it questions", async ({ page, browser }, info) => {
  const csp = watchCsp(page);
  await signUp(page, { business: `Ask Ltd ${info.project.name}` });
  const username = `mina${Date.now() % 100000}`;
  const { code, temp } = await addStaff(page, "Mina Akter", username);

  // Off until the owner chooses it.
  await page.goto("/app/ask");
  await expect(page.getByText("The assistant is off in this workspace")).toBeVisible();
  await expectAccessible(page, "ask: off");
  await page.getByRole("link", { name: "Open AI settings" }).click();
  await expect(page).toHaveURL(/tab=ai/);
  await page.getByRole("switch", { name: "Use the assistant" }).click();
  const terms = page.getByRole("dialog", { name: "Before you switch on the assistant" });
  await expect(terms.getByText(/sent to Google \(Gemini\)/)).toBeVisible();
  await expectAccessible(page, "ask: terms");
  await terms.getByRole("button", { name: "Accept and switch on" }).click();
  await expect(page.getByRole("switch", { name: "Use the assistant" })).toBeChecked();
  await expect(page.getByRole("switch", { name: "Questions" })).toBeChecked();
  await page.getByRole("switch", { name: "Weekly brief" }).click();
  await expect(page.getByRole("switch", { name: "Weekly brief" })).toBeChecked();
  await expectAccessible(page, "ask: settings");

  // The owner asks, and the answer links to where it came from.
  await page.goto("/app/ask");
  await expect(page.getByRole("heading", { name: "Ask", level: 1 })).toBeVisible();
  await page.getByRole("button", { name: "How many leave days do I have?" }).click();
  await expect(page.getByText("Here's what I found.")).toBeVisible();
  await expect(page.getByRole("link", { name: /\[1\]/ })).toHaveAttribute("href", "/app/leave");
  await expect(page.getByText(/1 of \d+ questions used this month/)).toBeVisible();
  await page.getByRole("button", { name: "Write this week's brief" }).click();
  await expect(page.getByText(/Reports, last 7 days looks steady\. \[1\]/)).toBeVisible();
  await expectAccessible(page, "ask: answered");

  // Staff ask in their own words; their questions are their own.
  const { context, staff } = await staffSignIn(browser, code, username, temp);
  await staff.goto("/app/ask");
  await expect(staff.getByRole("button", { name: "Write this week's brief" })).toHaveCount(0);
  await staff.getByLabel("Your question").fill("What tasks do I have?");
  await staff.getByRole("button", { name: "Send" }).click();
  await expect(staff.getByText("Here's what I found.")).toBeVisible();
  await expect(staff.getByRole("button", { name: "What tasks do I have?", exact: true })).toBeVisible();
  await staff.getByRole("button", { name: "Delete “What tasks do I have?”" }).click();
  await expect(staff.getByText("Nothing yet.")).toBeVisible();
  await expectAccessible(staff, "ask: staff");
  await context.close();

  await page.reload();
  await expect(page.getByRole("button", { name: "What tasks do I have?", exact: true })).toHaveCount(0);
  expect(csp).toEqual([]);
});
