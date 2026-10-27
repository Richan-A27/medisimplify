import { BackendStatus } from "@/components/BackendStatus";
import { BookIcon, CheckIcon, LockIcon, ShieldIcon } from "@/components/icons";
import { PipelineOverview } from "@/components/PipelineOverview";
import { ReportUploader } from "@/components/ReportUploader";
import { SafetyNotice } from "@/components/SafetyNotice";

const PROMISES = [
  { icon: CheckIcon, title: "Values kept exactly", text: "Results, units and ranges are shown as printed. Nothing is rounded or invented." },
  { icon: BookIcon, title: "Cited references", text: "Background comes from MedlinePlus (U.S. National Library of Medicine), with links." },
  { icon: ShieldIcon, title: "Safety-checked", text: "Every summary is checked for diagnoses, treatment advice and false reassurance." },
  { icon: LockIcon, title: "Private by design", text: "Reports are processed in memory and never stored. Only test results reach the AI." },
];

export default function Home() {
  return (
    <>
      <section className="border-b border-border bg-gradient-to-b from-surface to-background">
        <div className="mx-auto grid w-full max-w-6xl gap-10 px-4 py-12 sm:px-6 sm:py-16 lg:grid-cols-[1.15fr_1fr] lg:items-center">
          <div>
            <p className="inline-flex items-center gap-2 rounded-full border border-brand/20 bg-brand-soft px-3 py-1 text-xs font-semibold uppercase tracking-wide text-brand-strong">
              Academic mini-project
            </p>
            <h1 className="mt-4 text-3xl font-bold tracking-tight text-foreground sm:text-5xl sm:leading-[1.1]">
              Understand your medical report in plain language
            </h1>
            <p className="mt-5 max-w-xl text-lg leading-8 text-muted">
              MediSimplify turns technical lab reports into clear, patient-friendly explanations, grounded in trusted
              public health references and honest about what it cannot tell you.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <a
                href="#analyse"
                className="rounded-lg bg-brand px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
              >
                Analyse a report
              </a>
              <a
                href="#how-it-works"
                className="rounded-lg border border-border bg-surface px-5 py-2.5 text-sm font-semibold text-foreground transition-colors hover:bg-subtle focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
              >
                How it works
              </a>
            </div>
          </div>

          <ul className="card grid gap-5 p-6 sm:grid-cols-2 sm:p-7">
            {PROMISES.map(({ icon: Icon, title, text }) => (
              <li key={title}>
                <span className="flex size-9 items-center justify-center rounded-lg bg-brand-soft text-brand">
                  <Icon className="size-5" />
                </span>
                <p className="mt-3 font-semibold">{title}</p>
                <p className="mt-1 text-sm leading-6 text-muted">{text}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <div className="mx-auto flex w-full max-w-6xl flex-col gap-14 px-4 py-10 sm:px-6 sm:py-12">
        <SafetyNotice />
        <ReportUploader />
        <PipelineOverview />
        <BackendStatus />
      </div>
    </>
  );
}
