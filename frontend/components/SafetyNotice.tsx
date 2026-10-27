import { InfoIcon } from "@/components/icons";

export function SafetyNotice() {
  return (
    <aside
      aria-label="Medical disclaimer"
      className="flex gap-3 rounded-xl border border-warning-border bg-warning-bg px-5 py-4 text-warning-fg"
    >
      <InfoIcon className="mt-0.5 size-5 shrink-0" />
      <div>
        <p className="font-semibold">Educational prototype — not medical advice</p>
        <p className="mt-1 text-sm leading-6">
          MediSimplify explains report wording in plain language. It does not diagnose conditions, recommend
          treatment, or confirm that results are normal. Always discuss your report with a qualified healthcare
          professional. Use synthetic or de-identified reports only; do not upload identifiable patient data.
        </p>
      </div>
    </aside>
  );
}
