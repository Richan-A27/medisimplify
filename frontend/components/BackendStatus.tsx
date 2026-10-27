"use client";

import { useEffect, useState } from "react";

import { API_BASE_URL, ApiError, getHealth } from "@/lib/api";
import type { HealthResponse } from "@/types/api";

type Status =
  | { kind: "checking" }
  | { kind: "online"; health: HealthResponse; checkedAt: Date }
  | { kind: "offline"; message: string };

const START_COMMAND = "cd backend && .venv/bin/uvicorn app.main:app --reload";

export function BackendStatus() {
  const [status, setStatus] = useState<Status>({ kind: "checking" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getHealth(controller.signal)
      .then((health) => setStatus({ kind: "online", health, checkedAt: new Date() }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        const message =
          error instanceof ApiError ? error.message : "Unexpected error while contacting the backend.";
        setStatus({ kind: "offline", message });
      });
    return () => controller.abort();
  }, [attempt]);

  const retry = () => {
    setStatus({ kind: "checking" });
    setAttempt((n) => n + 1);
  };

  return (
    <section
      aria-labelledby="backend-status-heading"
      className="rounded-2xl border border-border bg-surface p-6 shadow-sm"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="backend-status-heading" className="text-lg font-semibold">
          System status
        </h2>
        <button
          type="button"
          onClick={retry}
          disabled={status.kind === "checking"}
          className="rounded-lg border border-border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-brand-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-60"
        >
          {status.kind === "checking" ? "Checking…" : "Check again"}
        </button>
      </div>

      <div role="status" aria-live="polite" aria-busy={status.kind === "checking"} className="mt-4">
        {status.kind === "checking" && (
          <p className="flex items-center gap-2 text-muted">
            <StatusDot tone="pending" />
            Contacting the backend at <code className="font-mono text-sm">{API_BASE_URL}</code>…
          </p>
        )}

        {status.kind === "offline" && (
          <div className="space-y-3">
            <p className="flex items-center gap-2 font-medium text-danger">
              <StatusDot tone="danger" />
              Backend unavailable
            </p>
            <p className="text-sm text-muted">{status.message}</p>
            <p className="text-sm text-muted">
              Start it from the project folder with:
              <code className="mt-1 block overflow-x-auto rounded-md bg-background px-3 py-2 font-mono text-xs">
                {START_COMMAND}
              </code>
            </p>
          </div>
        )}

        {status.kind === "online" && <OnlineDetails health={status.health} checkedAt={status.checkedAt} />}
      </div>
    </section>
  );
}

function OnlineDetails({ health, checkedAt }: { health: HealthResponse; checkedAt: Date }) {
  const llmReady = health.llm.api_key_configured;
  return (
    <div className="space-y-4">
      <p className="flex items-center gap-2 font-medium text-success">
        <StatusDot tone="success" />
        Backend online
        <span className="text-sm font-normal text-muted">
          · v{health.version} · {health.environment}
        </span>
      </p>

      <dl className="grid gap-3 text-sm sm:grid-cols-2">
        <div className="rounded-lg bg-background p-3">
          <dt className="text-muted">Language model</dt>
          <dd className="mt-1 font-medium">
            {health.llm.provider} · <span className="font-mono">{health.llm.model}</span>
          </dd>
        </div>
        <div className="rounded-lg bg-background p-3">
          <dt className="text-muted">API key</dt>
          <dd className={`mt-1 font-medium ${llmReady ? "text-success" : "text-warning-fg"}`}>
            {llmReady ? "Configured" : "Not configured"}
          </dd>
        </div>
        <div className="rounded-lg bg-background p-3">
          <dt className="text-muted">Reference library</dt>
          <dd className={`mt-1 font-medium ${health.knowledge_base.index_ready ? "" : "text-warning-fg"}`}>
            {health.knowledge_base.index_ready
              ? `${health.knowledge_base.source_count} sources · ${health.knowledge_base.chunk_count} passages`
              : "Not built"}
          </dd>
        </div>
        <div className="rounded-lg bg-background p-3">
          <dt className="text-muted">Maximum PDF size</dt>
          <dd className="mt-1 font-medium">{health.limits.max_upload_mb} MB</dd>
        </div>
        <div className="rounded-lg bg-background p-3">
          <dt className="text-muted">Last checked</dt>
          <dd className="mt-1 font-medium">{checkedAt.toLocaleTimeString()}</dd>
        </div>
      </dl>

      {!llmReady && (
        <p className="text-sm text-muted">
          Summaries need a Gemini API key. Add <code className="font-mono">GEMINI_API_KEY</code> to{" "}
          <code className="font-mono">.env</code> and restart the backend. Everything else works without it.
        </p>
      )}
    </div>
  );
}

function StatusDot({ tone }: { tone: "pending" | "success" | "danger" }) {
  const color = { pending: "bg-muted animate-pulse", success: "bg-success", danger: "bg-danger" }[tone];
  return <span aria-hidden="true" className={`inline-block size-2.5 shrink-0 rounded-full ${color}`} />;
}
