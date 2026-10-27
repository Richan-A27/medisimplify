import { expect, test } from "@playwright/test";

import { uploadAndExtract } from "./helpers";

test("results are readable on a phone without horizontal scrolling", async ({ page, request }) => {
  await page.goto("/");
  await uploadAndExtract(page, request, "metabolic_abnormal");

  const cards = page.getByRole("list", { name: "Test results" });
  await expect(cards).toBeVisible();
  await expect(cards.getByText("Glucose, Fasting")).toBeVisible();
  await expect(page.locator("table")).toBeHidden();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});
