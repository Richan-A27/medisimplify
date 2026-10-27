export type StepStatus = "pending" | "active" | "done" | "warning" | "error" | "skipped";

export interface StepState {
  status: StepStatus;
  detail?: string;
}

const ICONS: Record<StepStatus, { symbol: string; className: string; label: string }> = {
  pending: { symbol: "", className: "border-border text-muted", label: "Not started" },
  active: { symbol: "", className: "border-brand animate-pulse", label: "In progress" },
  done: { symbol: "✓", className: "border-brand bg-brand text-white dark:text-background", label: "Done" },
  warning: { symbol: "!", className: "border-warning-border bg-warning-bg text-warning-fg", label: "Needs attention" },
  error: { symbol: "✕", className: "border-danger bg-danger/10 text-danger", label: "Problem" },
  skipped: { symbol: "–", className: "border-border text-muted", label: "Skipped" },
};

export function ProgressSteps({ steps }: { steps: { label: string; state: StepState }[] }) {
  return (
    <ol className="mt-4 grid gap-3 sm:grid-cols-5" aria-label="Processing progress">
      {steps.map(({ label, state }) => {
        const icon = ICONS[state.status];
        return (
          <li key={label} className="flex items-start gap-2 sm:flex-col">
            <span
              aria-hidden="true"
              className={`flex size-6 shrink-0 items-center justify-center rounded-full border-2 text-xs font-bold ${icon.className}`}
            >
              {icon.symbol}
            </span>
            <span className="text-sm">
              <span className="font-medium">{label}</span>
              <span className="sr-only"> — {icon.label}.</span>
              {state.detail && <span className="block text-xs text-muted">{state.detail}</span>}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
