import { expect, test } from "@playwright/test";

import { API, appAlert, fixture, mockLlmConfigured, uploadAndExtract } from "./helpers";

test.describe("landing page", () => {
  test("shows the introduction, safety notice and live system status", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByRole("heading", { level: 1 })).toHaveText(/plain language/);
    await expect(page.getByLabel("Medical disclaimer")).toContainText("not medical advice");
    await expect(page.getByText("Backend online")).toBeVisible();
    await expect(page.getByText(/\d+ sources · \d+ passages/)).toBeVisible();
  });

  test("reports an unreachable backend", async ({ page }) => {
    await page.route(`${API}/api/health`, (route) => route.abort("connectionrefused"));
    await page.goto("/");

    await expect(page.getByText("Backend unavailable")).toBeVisible();
    await expect(page.getByText(/Cannot reach the backend/)).toBeVisible();
  });
});

test.describe("report processing (real backend)", () => {
  test("extracts values exactly and retrieves cited references", async ({ page, request }) => {
    await page.goto("/");
    await uploadAndExtract(page, request, "metabolic_abnormal");

    const progress = page.getByRole("list", { name: "Processing progress" });
    await expect(progress).toContainText("6 found");
    await expect(progress).toContainText(/\d+ passages/);

    const table = page.locator("table");
    const glucose = table.getByRole("row", { name: /Glucose, Fasting/ });
    await expect(glucose).toContainText("128");
    await expect(glucose).toContainText("mg/dL");
    await expect(glucose).toContainText("70 - 99");
    await expect(glucose).toContainText("H (high)");
    await expect(table.getByRole("row", { name: /LDL Cholesterol/ })).toContainText("Above range");

    const evidence = page.locator("section", { has: page.getByRole("heading", { name: "Reference information" }) });
    await expect(evidence.getByRole("heading", { name: "Glucose, Fasting" })).toBeVisible();
    const source = evidence.getByRole("link", { name: "Source: MedlinePlus, National Library of Medicine" }).first();
    await expect(source).toHaveAttribute("href", /^https:\/\/medlineplus\.gov\/lab-tests\//);
  });

  test("loads a synthetic sample from the picker", async ({ page }) => {
    await page.goto("/");
    await page.getByLabel(/Try a synthetic sample/).selectOption("cbc_normal");
    await page.getByRole("button", { name: "Use sample" }).click();

    await expect(page.getByText("synthetic-cbc_normal.pdf")).toBeVisible();
    await page.getByRole("button", { name: "Extract report" }).click();
    await expect(page.getByRole("list", { name: "Processing progress" })).toContainText("4 found");
  });

  test("marks conflicting values for checking", async ({ page, request }) => {
    await page.goto("/");
    await uploadAndExtract(page, request, "conflicting_values");

    await expect(page.getByText(/ambiguous or conflicting/)).toBeVisible();
    await expect(page.locator("table").getByText("Check source").first()).toBeVisible();
    await expect(page.locator("table").getByText("Report flag disagrees with the range")).toBeVisible();
  });

  test("flags instructions hidden in a report", async ({ page, request }) => {
    await page.goto("/");
    await uploadAndExtract(page, request, "prompt_injection");

    await expect(page.getByText(/resembles instructions to an AI system/)).toBeVisible();
  });

  test("explains when no test results are found", async ({ page, request }) => {
    await page.goto("/");
    await uploadAndExtract(page, request, "no_results");

    await expect(page.getByText("No test results to summarise")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Plain-language summary" })).toHaveCount(0);
  });

  test("rejects a scanned PDF with a clear message", async ({ page, request }) => {
    await page.goto("/");
    await uploadAndExtract(page, request, "scanned_image_only");

    await expect(appAlert(page)).toContainText("scanned");
  });

  test("rejects a non-PDF file before upload", async ({ page }) => {
    await page.goto("/");
    await page.locator("#report-file").setInputFiles({ name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("hello") });

    await expect(appAlert(page)).toHaveText("Please choose a PDF file.");
    await expect(page.getByRole("button", { name: "Extract report" })).toBeDisabled();
  });

  test("clear report resets the page", async ({ page, request }) => {
    await page.goto("/");
    await uploadAndExtract(page, request, "cbc_normal");
    await expect(page.locator("table")).toBeVisible();

    await page.getByRole("button", { name: "Clear report" }).click();

    await expect(page.locator("table")).toHaveCount(0);
    await expect(page.getByText("Choose a PDF or drag it here")).toBeVisible();
  });
});

test.describe("summary", () => {
  test("is disabled with guidance when no API key is configured", async ({ page, request }) => {
    const health = await (await request.get(`${API}/api/health`)).json();
    test.skip(health.llm.api_key_configured, "Backend has a Gemini key; this test covers the no-key state.");

    await page.goto("/");
    await uploadAndExtract(page, request, "metabolic_abnormal");

    await expect(page.getByText(/Summaries need a Gemini API key/).last()).toBeVisible();
    await expect(page.getByRole("button", { name: "Generate summary" })).toBeDisabled();
    await expect(page.getByRole("list", { name: "Processing progress" })).toContainText("API key not configured");
  });

  test("renders a validated summary with citations (mocked model response)", async ({ page, request }) => {
    await mockLlmConfigured(page);
    await page.route(`${API}/api/reports/summarize`, (route) => route.fulfill({ json: fixture("summary-passed") }));
    await page.goto("/");
    await uploadAndExtract(page, request, "metabolic_abnormal");

    await page.getByText("Few-shot").click();
    await page.getByRole("button", { name: "Generate summary" }).click();

    await expect(page.getByText("Automated checks passed")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Your results explained" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Questions to ask your healthcare professional" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Sources" })).toBeVisible();
    const citation = page.locator('a[href^="#source-E"]').first();
    await expect(citation).toBeVisible();
    await expect(page.getByText(/not a diagnosis or medical advice/)).toBeVisible();
    await expect(page.getByRole("list", { name: "Processing progress" })).toContainText("Checks passed");
  });

  test("hides a summary that failed safety checks until the reviewer asks", async ({ page, request }) => {
    await mockLlmConfigured(page);
    await page.route(`${API}/api/reports/summarize`, (route) => route.fulfill({ json: fixture("summary-failed") }));
    await page.goto("/");
    await uploadAndExtract(page, request, "metabolic_abnormal");
    await page.getByRole("button", { name: "Generate summary" }).click();

    await expect(page.getByText("This summary failed safety checks and is hidden")).toBeVisible();
    await expect(page.getByText(/Claims results are normal or healthy/)).toBeVisible();
    await expect(page.getByRole("heading", { name: "Your results explained" })).toHaveCount(0);

    await page.getByRole("button", { name: "Show the rejected output for review" }).click();
    await expect(page.getByText("Rejected output — shown for review only.")).toBeVisible();
  });

  for (const [status, code, message] of [
    [429, "llm_quota_exceeded", "The Gemini API quota or rate limit was reached. Wait a minute and try again."],
    [504, "llm_timeout", "The language model did not respond in time. Please try again."],
  ] as const) {
    test(`shows the ${code} error`, async ({ page, request }) => {
      await mockLlmConfigured(page);
      await page.route(`${API}/api/reports/summarize`, (route) => route.fulfill({ status, json: { code, message } }));
      await page.goto("/");
      await uploadAndExtract(page, request, "metabolic_abnormal");
      await page.getByRole("button", { name: "Generate summary" }).click();

      await expect(appAlert(page)).toHaveText(message);
      await expect(page.getByRole("list", { name: "Processing progress" })).toContainText("Not generated");
    });
  }
});
