import { readFileSync } from "node:fs";
import path from "node:path";

import { expect, type APIRequestContext, type Page } from "@playwright/test";

export const API = "http://localhost:8000";

export function fixture(name: string): unknown {
  return JSON.parse(readFileSync(path.join(__dirname, "fixtures", `${name}.json`), "utf8"));
}

/** Fetch a synthetic sample PDF from the backend so the test uploads real bytes. */
export async function samplePdf(request: APIRequestContext, id: string) {
  const response = await request.get(`${API}/api/samples/${id}`);
  expect(response.ok()).toBeTruthy();
  return { name: `${id}.pdf`, mimeType: "application/pdf", buffer: await response.body() };
}

export async function uploadAndExtract(page: Page, request: APIRequestContext, id: string) {
  await page.locator("#report-file").setInputFiles(await samplePdf(request, id));
  await page.getByRole("button", { name: "Extract report" }).click();
}

/** Pretend the backend has an API key so the summary button is enabled (summaries are mocked). */
export async function mockLlmConfigured(page: Page) {
  await page.route(`${API}/api/health`, async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.llm.api_key_configured = true;
    await route.fulfill({ response, json: body });
  });
}

/** Alerts rendered by the app (excludes Next.js's own route announcer, which also has role="alert"). */
export function appAlert(page: Page) {
  return page.locator('main [role="alert"]');
}
