"use client";

import { useState } from "react";

import { EvidencePanel } from "@/components/EvidencePanel";
import { ProgressSteps, type StepState } from "@/components/ProgressSteps";
import { SummaryPanel } from "@/components/SummaryPanel";
import type { ExtractionResponse, Measurement, MeasurementIssue, RangeComparison, SourceStatus } from "@/types/api";

const ISSUE_LABELS: Record<MeasurementIssue, string> = {
  missing_unit: "No unit printed",
  missing_reference_range: "No reference range printed",
  value_is_bound: "Value is a limit (e.g. <0.5)",
  multiple_ranges_found: "More than one range on the line",
  flag_conflicts_with_range: "Report flag disagrees with the range",
  duplicate_test_conflicting_values: "Test appears more than once with different values",
  unrecognized_text: "Line contains unrecognised text",
};

const COMPARISON_LABELS: Record<RangeComparison, string> = {
  above_range: "Above range",
  below_range: "Below range",
  within_range: "Within range",
  not_compared: "Not compared",
};

const STATUS_STYLES: Record<SourceStatus, { label: string; className: string }> = {
  complete: { label: "Complete", className: "bg-brand-soft text-brand-strong" },
  incomplete: { label: "Incomplete", className: "bg-warning-bg text-warning-fg" },
  ambiguous: { label: "Check source", className: "bg-danger/10 text-danger" },
};

export function ExtractionResults({ result, file }: { result: ExtractionResponse; file: File }) {
  const [evidenceState, setEvidenceState] = useState<StepState>({ status: "active", detail: "Searching…" });
  const [summaryState, setSummaryState] = useState<StepState>({ status: "pending", detail: "Choose a strategy below" });
  const hasResults = result.measurements.length > 0;
  const testNames = [...new Set(result.measurements.map((m) => m.test_name))];

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
        <h3 className="text-lg font-semibold">Processing</h3>
        <ProgressSteps
          steps={[
            { label: "File checked", state: { status: "done", detail: "Valid PDF" } },
            {
              label: "Text extracted",
              state: {
                status: "done",
                detail: `${result.page_count} page${result.page_count === 1 ? "" : "s"}, ${result.character_count.toLocaleString()} characters`,
              },
            },
            {
              label: "Test results recognised",
              state: hasResults
                ? { status: "done", detail: `${result.measurements.length} found` }
                : { status: "error", detail: "None found" },
            },
            { label: "References retrieved", state: hasResults ? evidenceState : { status: "skipped", detail: "Skipped" } },
            { label: "Summary generated and checked", state: hasResults ? summaryState : { status: "skipped", detail: "Skipped" } },
          ]}
        />

        {result.warnings.length > 0 && (
          <ul className="mt-5 space-y-2" aria-label="Warnings">
            {result.warnings.map((warning, index) => (
              <li
                key={`${warning.code}-${warning.page_number ?? "doc"}-${index}`}
                className="rounded-lg border border-warning-border bg-warning-bg px-3 py-2 text-sm text-warning-fg"
              >
                {warning.page_number !== null && <strong>Page {warning.page_number}: </strong>}
                {warning.message}
              </li>
            ))}
          </ul>
        )}
      </div>

      {hasResults ? (
        <>
          <SummaryPanel file={file} onStateChange={setSummaryState} />
          <MeasurementsTable measurements={result.measurements} />
          <EvidencePanel testNames={testNames} onStateChange={setEvidenceState} />
        </>
      ) : (
        <div className="rounded-2xl border border-dashed border-border bg-surface p-6 text-sm">
          <p className="font-semibold">No test results to summarise</p>
          <p className="mt-1 text-muted">
            MediSimplify recognises results written on one line, such as{" "}
            <code className="font-mono">Hemoglobin 13.8 g/dL 12.0 - 15.5</code>. Check the extracted text below; this
            report may use a layout that is not supported yet, or it may not contain lab results.
          </p>
        </div>
      )}

      <section aria-labelledby="text-heading" className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
        <h3 id="text-heading" className="text-lg font-semibold">
          Extracted text
        </h3>
        <p className="mt-1 text-sm text-muted">Review this against your original report.</p>
        <div className="mt-4 space-y-2">
          {result.pages.map((page) => (
            <details key={page.page_number} open={!hasResults && page.page_number === 1} className="rounded-lg bg-background">
              <summary className="cursor-pointer px-3 py-2 text-sm font-medium">
                Page {page.page_number}
                {!page.has_text && <span className="text-muted"> · no readable text</span>}
              </summary>
              <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words px-3 pb-3 font-mono text-xs leading-5">
                {page.text || "(empty)"}
              </pre>
            </details>
          ))}
        </div>
      </section>
    </div>
  );
}

function MeasurementsTable({ measurements }: { measurements: Measurement[] }) {
  return (
    <section aria-labelledby="results-heading" className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
      <h3 id="results-heading" className="text-lg font-semibold">
        Test results found in the report
      </h3>
      <p className="mt-1 text-sm text-muted">
        Values, units and ranges are shown exactly as printed. &ldquo;Range check&rdquo; is simple arithmetic against
        the printed range, separate from any flag the laboratory printed. It is not a diagnosis.
      </p>

      {/* Cards on small screens */}
      <ul className="mt-4 space-y-3 md:hidden" aria-label="Test results">
        {measurements.map((m, index) => (
          <li key={`${m.page_number}-${index}`} className="rounded-lg bg-background p-4 text-sm">
            <div className="flex items-start justify-between gap-2">
              <p className="font-semibold">{m.test_name}</p>
              <StatusBadge status={m.source_status} />
            </div>
            <p className="mt-1">
              <span className="font-mono text-base">{m.value}</span> {m.unit ?? <Missing />}
            </p>
            <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
              <dt className="text-muted">Reference range</dt>
              <dd>{m.reference_range ?? <Missing />}</dd>
              <dt className="text-muted">Report flag</dt>
              <dd>{m.reported_flag ? `${m.reported_flag} (${m.flag_meaning})` : "None"}</dd>
              <dt className="text-muted">Range check</dt>
              <dd>{COMPARISON_LABELS[m.range_comparison]}</dd>
              <dt className="text-muted">Page</dt>
              <dd>{m.page_number}</dd>
            </dl>
            <IssueList issues={m.issues} />
          </li>
        ))}
      </ul>

      {/* Table on wider screens */}
      <div className="mt-4 hidden overflow-x-auto md:block">
        <table className="w-full border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-border text-muted">
              <th scope="col" className="py-2 pr-4 font-medium">Test</th>
              <th scope="col" className="py-2 pr-4 font-medium">Result</th>
              <th scope="col" className="py-2 pr-4 font-medium">Unit</th>
              <th scope="col" className="py-2 pr-4 font-medium">Reference range</th>
              <th scope="col" className="py-2 pr-4 font-medium">Report flag</th>
              <th scope="col" className="py-2 pr-4 font-medium">Range check</th>
              <th scope="col" className="py-2 font-medium">Source status</th>
            </tr>
          </thead>
          <tbody>
            {measurements.map((m, index) => (
              <tr key={`${m.page_number}-${index}`} className="border-b border-border align-top last:border-0">
                <th scope="row" className="py-3 pr-4 font-medium">
                  {m.test_name}
                  <span className="block text-xs font-normal text-muted">Page {m.page_number}</span>
                </th>
                <td className="py-3 pr-4 font-mono">{m.value}</td>
                <td className="py-3 pr-4">{m.unit ?? <Missing />}</td>
                <td className="py-3 pr-4">{m.reference_range ?? <Missing />}</td>
                <td className="py-3 pr-4">
                  {m.reported_flag ? (
                    <span>
                      {m.reported_flag} <span className="text-muted">({m.flag_meaning})</span>
                    </span>
                  ) : (
                    <span className="text-muted">None</span>
                  )}
                </td>
                <td className="py-3 pr-4">{COMPARISON_LABELS[m.range_comparison]}</td>
                <td className="py-3">
                  <StatusBadge status={m.source_status} />
                  <IssueList issues={m.issues} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function StatusBadge({ status }: { status: SourceStatus }) {
  const style = STATUS_STYLES[status];
  return (
    <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${style.className}`}>{style.label}</span>
  );
}

function IssueList({ issues }: { issues: MeasurementIssue[] }) {
  if (issues.length === 0) return null;
  return (
    <ul className="mt-1 space-y-0.5 text-xs text-muted">
      {issues.map((issue) => (
        <li key={issue}>{ISSUE_LABELS[issue]}</li>
      ))}
    </ul>
  );
}

function Missing() {
  return <span className="text-muted">Not printed</span>;
}
