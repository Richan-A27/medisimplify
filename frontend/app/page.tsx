import { BackendStatus } from "@/components/BackendStatus";
import { PipelineOverview } from "@/components/PipelineOverview";
import { ReportUploader } from "@/components/ReportUploader";
import { SafetyNotice } from "@/components/SafetyNotice";

export default function Home() {
  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-10 px-4 py-10 sm:px-6 sm:py-14">
      <section aria-labelledby="intro-heading" className="max-w-3xl">
        <p className="text-sm font-semibold uppercase tracking-wide text-brand">Academic mini-project</p>
        <h1 id="intro-heading" className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">
          Understand your medical report in plain language
        </h1>
        <p className="mt-4 text-lg leading-8 text-muted">
          MediSimplify converts technical lab reports into patient-friendly explanations. It keeps your
          original values, units and reference ranges intact, grounds background information in cited
          public health references, and is clear about what it cannot tell you.
        </p>
      </section>

      <SafetyNotice />
      <ReportUploader />
      <BackendStatus />
      <PipelineOverview />
    </div>
  );
}
