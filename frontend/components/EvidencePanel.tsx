"use client";

import { useEffect, useState } from "react";

import type { StepState } from "@/components/ProgressSteps";
import { ApiError, retrieveEvidence } from "@/lib/api";
import type { EvidencePassage, EvidenceResponse } from "@/types/api";

type State =
  | { kind: "loading" }
  | { kind: "ready"; evidence: EvidenceResponse }
  | { kind: "error"; message: string };

export function EvidencePanel({
  testNames,
  onStateChange,
}: {
  testNames: string[];
  onStateChange?: (state: StepState) => void;
}) {
  const [state, setState] = useState<State>({ kind: "loading" });
  const key = testNames.join("\u0000");

  useEffect(() => {
    const controller = new AbortController();
    retrieveEvidence(key.split("\u0000"), controller.signal)
      .then((evidence) => {
        setState({ kind: "ready", evidence });
        const missing = evidence.unmatched_tests.length;
        onStateChange?.({
          status: missing ? "warning" : "done",
          detail: `${evidence.passages.length} passages${missing ? `; ${missing} test${missing === 1 ? "" : "s"} without references` : ""}`,
        });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setState({
          kind: "error",
          message: error instanceof ApiError ? error.message : "Reference information could not be loaded.",
        });
        onStateChange?.({ status: "error", detail: "Unavailable" });
      });
    return () => controller.abort();
  }, [key, onStateChange]);

  return (
    <section aria-labelledby="evidence-heading" className="card p-6">
      <h3 id="evidence-heading" className="text-lg font-semibold">
        Reference information
      </h3>
      <p className="mt-1 text-sm text-muted">
        General background about each test from a curated public library. It describes the test, not your
        result, and is not evidence that you have any condition.
      </p>

      <div role="status" aria-live="polite" aria-busy={state.kind === "loading"} className="mt-4">
        {state.kind === "loading" && (
          <p className="flex items-center gap-2 text-sm text-muted">
            <span aria-hidden="true" className="size-2.5 animate-pulse rounded-full bg-brand" />
            Searching the reference library… The first search can take a few seconds.
          </p>
        )}
        {state.kind === "error" && (
          <p role="alert" className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">
            {state.message}
          </p>
        )}
      </div>

      {state.kind === "ready" && <EvidenceList evidence={state.evidence} />}
    </section>
  );
}

function EvidenceList({ evidence }: { evidence: EvidenceResponse }) {
  const passages = new Map(evidence.passages.map((p) => [p.citation_id, p]));

  return (
    <div className="space-y-5">
      {evidence.tests
        .filter((test) => test.citation_ids.length > 0)
        .map((test) => (
          <div key={test.test_name}>
            <h4 className="font-semibold">{test.test_name}</h4>
            <ul className="mt-2 space-y-2">
              {test.citation_ids.map((id) => {
                const passage = passages.get(id);
                return passage ? <PassageItem key={id} passage={passage} /> : null;
              })}
            </ul>
          </div>
        ))}

      {evidence.unmatched_tests.length > 0 && (
        <p className="rounded-lg border border-warning-border bg-warning-bg px-3 py-2 text-sm text-warning-fg">
          No sufficiently relevant reference was found for: {evidence.unmatched_tests.join(", ")}. No background
          information is shown for {evidence.unmatched_tests.length === 1 ? "this test" : "these tests"}.
        </p>
      )}
    </div>
  );
}

function PassageItem({ passage }: { passage: EvidencePassage }) {
  return (
    <li className="rounded-lg border border-border bg-subtle p-3 text-sm">
      <details>
        <summary className="cursor-pointer">
          <span className="mr-2 rounded bg-brand-soft px-1.5 py-0.5 font-mono text-xs text-brand-strong">
            {passage.citation_id}
          </span>
          <span className="font-medium">{passage.section}</span>
          <span className="text-muted"> · {passage.title}</span>
        </summary>
        <p className="mt-2 whitespace-pre-line leading-6">{passage.text}</p>
      </details>
      <p className="mt-2 text-xs text-muted">
        <a href={passage.url} target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">
          {passage.attribution}
        </a>{" "}
        · relevance {passage.similarity.toFixed(2)}
      </p>
    </li>
  );
}
