import type {
  ApiErrorBody,
  EvidenceResponse,
  ExtractionResponse,
  HealthResponse,
  SampleInfo,
  Strategy,
  SummaryResponse,
} from "@/types/api";

const DEFAULT_API_BASE_URL = "http://localhost:8000";
const DEFAULT_TIMEOUT_MS = 8_000;
const EXTRACTION_TIMEOUT_MS = 60_000;
// The first retrieval loads the embedding model on the server, which can take several seconds.
const EVIDENCE_TIMEOUT_MS = 60_000;
// Covers server-side extraction, retrieval and the LLM call (the backend's own LLM timeout is 60 s).
const SUMMARY_TIMEOUT_MS = 120_000;

// Inlined at build time (NEXT_PUBLIC_ prefix); restart `next dev` after changing it.
export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_BASE_URL
).replace(/\/+$/, "");

export type ApiErrorCode = "network_error" | "timeout" | "invalid_response" | string;

export class ApiError extends Error {
  readonly status: number | null;
  readonly code: ApiErrorCode;

  constructor(message: string, status: number | null, code: ApiErrorCode) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

function isAbortReason(error: unknown, name: "AbortError" | "TimeoutError"): boolean {
  return error instanceof DOMException && error.name === name;
}

async function requestJson<T>(
  path: string,
  { signal, timeoutMs = DEFAULT_TIMEOUT_MS, ...init }: RequestInit & { timeoutMs?: number } = {},
): Promise<T> {
  const timeout = AbortSignal.timeout(timeoutMs);
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
    });
  } catch (error) {
    if (isAbortReason(error, "AbortError")) throw error; // caller cancelled; not an API failure
    if (isAbortReason(error, "TimeoutError")) {
      throw new ApiError("The backend did not respond in time.", null, "timeout");
    }
    throw new ApiError(
      `Cannot reach the backend at ${API_BASE_URL}. Is it running?`,
      null,
      "network_error",
    );
  }

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as Partial<ApiErrorBody> | null;
    throw new ApiError(
      body?.message ?? `Request failed with status ${response.status}.`,
      response.status,
      body?.code ?? `http_${response.status}`,
    );
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError("The backend returned an unreadable response.", response.status, "invalid_response");
  }
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/api/health", { signal, cache: "no-store" });
}

/** Upload a PDF for text and measurement extraction. The backend does not store the file. */
export function extractReport(file: File, signal?: AbortSignal): Promise<ExtractionResponse> {
  const body = new FormData();
  body.append("file", file);
  return requestJson<ExtractionResponse>("/api/reports/extract", {
    method: "POST",
    body,
    signal,
    timeoutMs: EXTRACTION_TIMEOUT_MS,
  });
}

/** Retrieve general reference passages. Sends test names only, never values or patient details. */
export function retrieveEvidence(testNames: string[], signal?: AbortSignal): Promise<EvidenceResponse> {
  return requestJson<EvidenceResponse>("/api/evidence/retrieve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ test_names: testNames }),
    signal,
    timeoutMs: EVIDENCE_TIMEOUT_MS,
  });
}

/** Re-upload the PDF and ask the backend for a validated plain-language summary. */
export function summarizeReport(file: File, strategy: Strategy, signal?: AbortSignal): Promise<SummaryResponse> {
  const body = new FormData();
  body.append("file", file);
  body.append("strategy", strategy);
  return requestJson<SummaryResponse>("/api/reports/summarize", {
    method: "POST",
    body,
    signal,
    timeoutMs: SUMMARY_TIMEOUT_MS,
  });
}

export function listSamples(signal?: AbortSignal): Promise<SampleInfo[]> {
  return requestJson<SampleInfo[]>("/api/samples", { signal });
}

/** Download a synthetic sample report as a File, ready to upload like a user's own PDF. */
export async function fetchSample(id: string): Promise<File> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/samples/${encodeURIComponent(id)}`, {
      signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
    });
  } catch {
    throw new ApiError(`Cannot reach the backend at ${API_BASE_URL}. Is it running?`, null, "network_error");
  }
  if (!response.ok) throw new ApiError("The sample report could not be loaded.", response.status, "sample_error");
  return new File([await response.blob()], `synthetic-${id}.pdf`, { type: "application/pdf" });
}
