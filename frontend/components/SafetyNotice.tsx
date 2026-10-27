export function SafetyNotice() {
  return (
    <aside
      aria-label="Medical disclaimer"
      className="rounded-2xl border border-warning-border bg-warning-bg p-5 text-warning-fg"
    >
      <p className="font-semibold">Educational prototype — not medical advice</p>
      <p className="mt-1 text-sm leading-6">
        MediSimplify explains report wording in plain language. It does not diagnose conditions, recommend
        treatment, or confirm that results are normal. Always discuss your report with a qualified healthcare
        professional. Use synthetic or de-identified reports only; do not upload identifiable patient data.
      </p>
    </aside>
  );
}
