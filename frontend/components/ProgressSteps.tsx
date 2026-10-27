export type StepStatus = "pending" | "active" | "done" | "warning" | "error" | "skipped";

export interface StepState {
  status: StepStatus;
  detail?: string;
}

const ICONS: Record<StepStatus, { symbol: string; className: string; label: string }> = {
  pending: { symbol: "", className: "border-border bg-surface text-muted", label: "Not started" },
  active: { symbol: "", className: "border-brand bg-brand-soft animate-pulse", label: "In progress" },
  done: { symbol: "✓", className: "border-brand bg-brand text-white", label: "Done" },
  warning: { symbol: "!", className: "border-warning-border bg-warning-bg text-warning-fg", label: "Needs attention" },
  error: { symbol: "✕", className: "border-danger bg-danger-soft text-danger", label: "Problem" },
  skipped: { symbol: "–", className: "border-border bg-subtle text-muted", label: "Skipped" },
};

export function ProgressSteps({ steps }: { steps: { label: string; state: StepState }[] }) {
  return (
    <ol className="mt-4" aria-label="Processing progress">
      {steps.map(({ label, state }, index) => {
        const icon = ICONS[state.status];
        const last = index === steps.length - 1;
        return (
          <li key={label} className="relative flex gap-3 pb-4 last:pb-0">
            {!last && <span aria-hidden="true" className="absolute left-3 top-7 -bottom-0 w-px bg-border" />}
            <span
              aria-hidden="true"
              className={`relative flex size-6 shrink-0 items-center justify-center rounded-full border-2 text-xs font-bold ${icon.className}`}
            >
              {icon.symbol}
            </span>
            <span className="text-sm leading-6">
              <span className="font-medium">{label}</span>
              <span className="sr-only"> — {icon.label}.</span>
              {state.detail && <span className="block text-xs leading-5 text-muted">{state.detail}</span>}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
