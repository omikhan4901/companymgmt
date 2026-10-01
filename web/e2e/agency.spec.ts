import { execFileSync } from "node:child_process";

import { expect, test, type Browser, type Page } from "@playwright/test";

import { expectAccessible, watchCsp } from "./helpers";

interface Week {
  owner: { email: string; password: string; name: string };
  workspace_code: string;
  password: string;
  people: Record<string, string>;
  last_reader: string;
  waiting_leave: string;
  waiting_manager: string;
}

/** Plays the agency's week through the API (api/scripts/agency_week.py), stopping short of the end. */
function seedWeek(): Week {
  const out = execFileSync("uv", ["run", "--quiet", "python", "-m", "scripts.agency_week", "--api", "http://localhost:3000", "--leave-for-browser", "--json"], {
    cwd: "../api",
    encoding: "utf8",
    timeout: 180_000,
  });
  return JSON.parse(out.trim().split("\n").pop() ?? "{}") as Week;
}

async function staffIn(browser: Browser, week: Week, username: string): Promise<{ close: () => Promise<void>; staff: Page }> {
  const context = await browser.newContext({ baseURL: "http://localhost:3000", locale: "en-GB", timezoneId: "Asia/Dhaka" });
  const staff = await context.newPage();
  await staff.goto("/login");
  await staff.getByText("Staff sign-in (no email)").click();
  await staff.getByLabel("Workspace code").fill(week.workspace_code);
  await staff.getByLabel("Username").fill(username);
  await staff.getByLabel(/^Password$/).fill(week.password);
  await staff.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(staff.getByRole("heading", { name: /Hi/ })).toBeVisible();
  return { close: () => context.close(), staff };
}

test("a 30-person agency finishes its week in the product", async ({ page, browser }, info) => {
  // Seeding thirty people takes a while; the phone layouts are covered by the other journeys.
  test.skip(info.project.name !== "desktop", "desktop only");
  test.setTimeout(300_000);
  const week = seedWeek();
  expect(Object.keys(week.people)).toHaveLength(29);
  const csp = watchCsp(page);

  await page.goto("/login");
  await page.getByLabel("Email", { exact: true }).fill(week.owner.email);
  await page.getByLabel("Password", { exact: true }).fill(week.owner.password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/app$/);
  await expectAccessible(page, "agency: owner home");

  // Thursday afternoon: one person still has to read the policy.
  await page.goto("/app/documents");
  await page.getByRole("button", { name: /^Code of conduct/ }).first().click();
  await expect(page.getByRole("dialog", { name: "Code of conduct" }).getByText("Acknowledged by 29 of 30")).toBeVisible();
  await page.goto("/app/announcements");
  await expect(page.getByRole("button", { name: "Read by 29 of 30" })).toBeVisible();

  // Sumaiya reads the week's note and acknowledges the policy.
  const reader = await staffIn(browser, week, week.last_reader);
  await expect(reader.staff.getByText("To read")).toBeVisible();
  await reader.staff.goto("/app/announcements");
  await expect(reader.staff.getByText("This week: Shapla Eid campaign and the Meghna launch")).toBeVisible();
  await reader.staff.goto("/app/documents");
  await reader.staff.getByRole("button", { name: /^Code of conduct/ }).first().click();
  const doc = reader.staff.getByRole("dialog", { name: "Code of conduct" });
  await doc.getByRole("button", { name: "I've read and understood it" }).click();
  await expect(doc.getByText("You've acknowledged this version.")).toBeVisible();
  await reader.staff.goto("/app/tasks");
  await expect(reader.staff.getByRole("button", { name: /^Moodboard/ })).toHaveCount(0); // done, so not in My work
  await reader.close();

  // Nusrat approves the last leave request from her inbox.
  const manager = await staffIn(browser, week, week.waiting_manager);
  await manager.staff.goto("/app/approvals");
  const name = week.people[week.waiting_leave];
  await manager.staff.getByRole("button", { name: `Approve: ${name}` }).click();
  await expect(manager.staff.getByText("Nothing waiting for you")).toBeVisible();
  await expectAccessible(manager.staff, "agency: manager inbox, empty");
  await manager.close();

  // Everyone has read and acknowledged; the work and the new joiner are on track.
  await page.goto("/app/documents");
  await page.getByRole("button", { name: /^Code of conduct/ }).first().click();
  await expect(page.getByRole("dialog", { name: "Code of conduct" }).getByText("Acknowledged by 30 of 30")).toBeVisible();
  await page.goto("/app/announcements");
  await expect(page.getByRole("button", { name: "Read by 30 of 30" })).toBeVisible();
  await page.goto("/app/approvals");
  await expect(page.getByText("Nothing waiting for you")).toBeVisible();
  await page.goto("/app/tasks?tab=projects");
  for (const project of ["Meghna Bank website refresh", "Shapla Tea Eid campaign", "Padma Foods social calendar"]) {
    await expect(page.getByRole("button", { name: new RegExp(project) })).toBeVisible();
  }
  await expectAccessible(page, "agency: projects");
  await page.goto("/app/tasks?tab=onboarding");
  await expect(page.getByText("Mitu Chowdhury")).toBeVisible();
  await expect(page.getByText("1 of 3 done")).toBeVisible();
  expect(csp).toEqual([]);
});
