import { expect, test } from "@playwright/test";

import { expectAccessible, signUp, watchCsp } from "./helpers";

test("a shop adds an item, sells it at the till and sees it in the books", async ({ page }, info) => {
  const csp = watchCsp(page);
  await signUp(page, { business: `Tea Corner ${info.project.name}`, type: /Shop or tea stall/ });

  await page.goto("/app/settings?tab=modules");
  const books = page.getByRole("switch", { name: "Accounting", exact: true });
  await books.click();
  await expect(books).toBeChecked();

  await page.goto("/app/sales?tab=products");
  await page.getByRole("button", { name: "New item" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Name", { exact: true }).fill("Milk tea");
  await dialog.getByLabel("Price", { exact: true }).fill("25");
  await dialog.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("cell", { name: "Milk tea", exact: true })).toBeVisible();

  await page.goto("/app/pos");
  await page.getByLabel("Cash in the drawer now").fill("500");
  await page.getByRole("button", { name: "Open drawer" }).click();
  const tea = page.getByRole("region", { name: "Items" }).getByRole("button", { name: /Milk tea/ });
  await tea.click();
  await tea.click();
  await page.getByRole("button", { name: "Exact" }).click();
  await expectAccessible(page, "till with a sale");
  await page.getByRole("button", { name: "Complete sale" }).click();
  await expect(page.getByText(/Sold\. Change/)).toBeVisible();

  await page.goto("/app/sales");
  await expect(page.getByText(/1 sale, BDT\s?50/)).toBeVisible();

  await page.goto("/app/accounting");
  await expect(page.getByRole("heading", { level: 1, name: "Accounts" })).toBeVisible();
  await expectAccessible(page, "books");
  expect(csp).toEqual([]);
});
