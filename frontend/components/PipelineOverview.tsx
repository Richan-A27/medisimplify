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
    <section id="how-it-works" aria-labelledby="pipeline-heading">
      <h2 id="pipeline-heading" className="text-2xl font-semibold tracking-tight">
        How it works
      </h2>
      <p className="mt-1 text-sm text-muted">Six auditable stages from PDF to checked summary.</p>
      <ol className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {STAGES.map((stage, index) => (
          <li key={stage.title} className="card p-5 transition-shadow hover:shadow-md">
            <span
              aria-hidden="true"
              className="flex size-8 items-center justify-center rounded-lg bg-brand-soft text-sm font-semibold text-brand-strong ring-1 ring-brand/15"
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
