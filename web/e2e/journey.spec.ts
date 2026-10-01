import { expect, test } from "@playwright/test";

import { addStaff, expectAccessible, PASSWORD, signUp, watchCsp } from "./helpers";

test("an owner signs up, adds a staff member, and both see attendance", async ({ page, browser }, info) => {
  const csp = watchCsp(page);
  await signUp(page, { business: `Cha Ghor ${info.project.name}` });
  await expect(page.getByRole("heading", { name: /Hi Rahim/ })).toBeVisible();
  await expectAccessible(page, "home");

  // Owner clocks in from the home screen (no branch placed yet, so no location check).
  await page.getByRole("button", { name: "Clock in" }).click();
  await expect(page.getByText(/Clocked in since/)).toBeVisible();

  const username = `karim${Date.now() % 100000}`;
  await page.goto("/app/team");
  await expect(page.getByRole("heading", { name: "Team" })).toBeVisible();
  await expectAccessible(page, "team");
  const { code, temp } = await addStaff(page, "করিম মিয়া", username);

  // The staff member signs in on their own phone in Bangla and must choose a password.
  // After sign-in the account's saved language applies, so later steps accept either.
  const staffContext = await browser.newContext({ baseURL: "http://localhost:3000", locale: "bn-BD", timezoneId: "Asia/Dhaka" });
  const staff = await staffContext.newPage();
  await staff.goto("/login");
  await staff.getByText(/কর্মী সাইন-ইন/).click();
  await staff.getByLabel("ওয়ার্কস্পেস কোড").fill(code);
  await staff.getByLabel("ইউজারনেম").fill(username);
  await staff.getByLabel(/^পাসওয়ার্ড$/).fill(temp);
  await staff.getByRole("button", { name: "সাইন ইন", exact: true }).click();
  await expect(staff).toHaveURL(/change-password/);
  await staff.getByLabel(/^(বর্তমান পাসওয়ার্ড|Current password)$/).fill(temp);
  await staff.getByLabel(/^(নতুন পাসওয়ার্ড|New password)$/).fill(PASSWORD);
  await staff.getByRole("button", { name: /সংরক্ষণ|Save/ }).click();
  await expect(staff.getByRole("heading", { name: /হ্যালো|Hi/ })).toBeVisible();
  await expectAccessible(staff, "staff home (Bangla)");
  await staff.getByRole("button", { name: /হাজিরা দিন|Clock in/ }).click();
  await expect(staff.getByText(/থেকে কাজে আছেন|Clocked in since/)).toBeVisible();
  // Staff can't see the team page.
  await expect(staff.getByRole("link", { name: /^(টিম|Team)$/ })).toHaveCount(0);
  await staffContext.close();

  // The owner sees both people at work and the timesheet.
  await page.goto("/app/attendance?tab=today");
  await expect(page.getByText("করিম মিয়া").first()).toBeVisible();
  await expectAccessible(page, "attendance today");
  await page.goto("/app/attendance?tab=timesheet");
  await expect(page.getByRole("rowheader", { name: "করিম মিয়া" })).toBeVisible();

  for (const path of ["/app/people", "/app/people?tab=departments", "/app/settings", "/app/settings?tab=branches", "/app/settings?tab=plan", "/app/settings?tab=audit", "/app/account"]) {
    await page.goto(path);
    await expect(page.locator("main h1")).toBeVisible();
    await expectAccessible(page, path);
  }
  expect(csp).toEqual([]);
});

test("clock-in is checked against the branch location", async ({ page, browser }, info) => {
  await signUp(page, { business: `Location ${info.project.name}` });
  // Place the main branch where the owner is standing.
  await page.goto("/app/settings?tab=branches");
  await page.getByRole("button", { name: "Edit: Main branch" }).click();
  await page.getByRole("button", { name: "Use my current location" }).click();
  await expect(page.getByText(/Placed at your current location/)).toBeVisible();
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText(/Placed · 150 m/)).toBeVisible();

  const username = `nadia${Date.now() % 100000}`;
  const { code, temp } = await addStaff(page, "Nadia Rahman", username);

  // About 2 km north of the branch: refused, with the distance.
  const far = await browser.newContext({
    baseURL: "http://localhost:3000",
    timezoneId: "Asia/Dhaka",
    permissions: ["geolocation"],
    geolocation: { latitude: 23.7566, longitude: 90.3958, accuracy: 20 },
  });
  const staff = await far.newPage();
  await staff.goto("/login");
  await staff.getByText("Staff sign-in (no email)").click();
  await staff.getByLabel("Workspace code").fill(code);
  await staff.getByLabel("Username").fill(username);
  await staff.getByLabel("Password", { exact: true }).fill(temp);
  await staff.getByRole("button", { name: "Sign in", exact: true }).click();
  await staff.getByLabel("Current password").fill(temp);
  await staff.getByLabel("New password").fill(PASSWORD);
  await staff.getByRole("button", { name: "Save" }).click();
  await staff.getByRole("button", { name: "Clock in" }).click();
  await expect(staff.getByText(/You're about 2 km from Main branch/)).toBeVisible();

  // At the shop: accepted, and marked as at the branch.
  await far.setGeolocation({ latitude: 23.7388, longitude: 90.3958, accuracy: 15 });
  await staff.getByRole("button", { name: "Clock in" }).click();
  await expect(staff.getByText(/Clocked in since/)).toBeVisible();
  await expect(staff.getByText("At branch")).toBeVisible();
  await far.close();

  await page.goto("/app/attendance?tab=records");
  await expect(page.getByText("In: At branch").first()).toBeVisible();
});

test("dark mode and accents can be chosen and stay accessible", async ({ page }) => {
  await signUp(page, { business: "Dark Tea" });
  await page.goto("/app/account");
  await page.getByRole("radio", { name: "Dark" }).click();
  await page.getByRole("radio", { name: "Garnet" }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await expect(page.locator("html")).toHaveAttribute("data-accent", "garnet");
  await expectAccessible(page, "account (dark, garnet)");
  // The choice survives a reload (applied before the first paint).
  await page.reload();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.goto("/app");
  await expectAccessible(page, "home (dark, garnet)");
});

test("sign-in pages are accessible in both languages", async ({ page }) => {
  const csp = watchCsp(page);
  for (const path of ["/login", "/signup", "/forgot-password"]) {
    await page.goto(path);
    await expect(page.locator("h1")).toBeVisible();
    await expectAccessible(page, `${path} en`);
  }
  await page.goto("/login");
  await page.getByRole("button", { name: "বাংলা" }).click();
  await expect(page.getByRole("heading", { name: "আবার স্বাগতম" })).toBeVisible();
  await expectAccessible(page, "/login bn");
  expect(csp).toEqual([]);
});

test("wrong password shows one clear message", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email", { exact: true }).fill("nobody@example.com");
  await page.getByLabel("Password", { exact: true }).fill("not the right one");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("The sign-in details are incorrect.")).toBeVisible();
});

test("marketing pages are accessible and keep their security policy", async ({ page }) => {
  const csp = watchCsp(page);
  for (const path of ["/", "/pricing", "/privacy", "/terms"]) {
    const response = await page.goto(path);
    expect(response?.headers()["content-security-policy"], path).toContain("script-src 'self' 'sha256-");
    await expect(page.locator("h1")).toBeVisible();
    await expectAccessible(page, path);
  }
  expect(csp).toEqual([]);
});

test("typing before a form's data loads keeps what was typed", async ({ page }, info) => {
  await signUp(page, { business: `Slow Net ${info.project.name}` });
  // Roles arrive late, as on a slow connection.
  await page.route("**/v1/roles", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1500));
    await route.continue();
  });
  await page.goto("/app/team");
  await page.getByRole("button", { name: "Add staff without email" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Name", { exact: true }).fill("Late Loader");
  await dialog.getByLabel("Username", { exact: true }).fill(`late${Date.now() % 100000}`);
  await page.waitForResponse("**/v1/roles");
  await expect(dialog.getByLabel("Name", { exact: true })).toHaveValue("Late Loader");
  await dialog.getByRole("button", { name: "Add", exact: true }).click();
  await expect(dialog.getByText("Staff account created")).toBeVisible();
});
