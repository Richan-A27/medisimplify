type Stage = {
  title: string;
  description: string;
};

const STAGES: Stage[] = [
  {
    title: "Upload and validate",
    description: "Checks the file type, size and that the PDF contains readable text.",
  },
  {
    title: "Extract report facts",
    description: "Finds test names, values, units and reference ranges exactly as printed. Nothing is invented.",
  },
  {
    title: "Retrieve evidence",
    description: "Searches a curated library of reputable public health references (RAG).",
  },
  {
    title: "Generate explanation",
    description: "Gemini writes a plain-language summary using zero-shot, few-shot or RAG-enhanced prompts.",
  },
  {
    title: "Validate safety",
    description: "Checks values against the report, verifies citations and flags unsupported claims.",
  },
  {
    title: "Review results",
    description: "Shows the summary, results table, cited sources, uncertainties and questions for your doctor.",
  },
];

export function PipelineOverview() {
  return (
    <section aria-labelledby="pipeline-heading">
      <h2 id="pipeline-heading" className="text-xl font-semibold">
        How it works
      </h2>
      <ol className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {STAGES.map((stage, index) => (
          <li key={stage.title} className="rounded-2xl border border-border bg-surface p-5">
            <span
              aria-hidden="true"
              className="flex size-8 items-center justify-center rounded-full bg-brand-soft text-sm font-semibold text-brand-strong"
            >
              {index + 1}
            </span>
            <h3 className="mt-3 font-semibold">{stage.title}</h3>
            <p className="mt-1 text-sm leading-6 text-muted">{stage.description}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
