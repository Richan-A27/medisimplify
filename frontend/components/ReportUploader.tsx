"use client";

import { useEffect, useRef, useState, type ChangeEvent, type DragEvent, type FormEvent } from "react";

import { ExtractionResults } from "@/components/ExtractionResults";
import { ApiError, extractReport, fetchSample, listSamples } from "@/lib/api";
import type { ExtractionResponse, SampleInfo } from "@/types/api";

// Client-side sanity cap only; the backend enforces the configured limit.
const HARD_MAX_BYTES = 50 * 1024 * 1024;

type State =
  | { kind: "idle" }
  | { kind: "processing" }
  | { kind: "success"; result: ExtractionResponse }
  | { kind: "error"; message: string };

function validateFile(file: File): string | null {
  const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
  if (!isPdf) return "Please choose a PDF file.";
  if (file.size === 0) return "The selected file is empty.";
  if (file.size > HARD_MAX_BYTES) return "The file is too large.";
  return null;
}

export function ReportUploader() {
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<State>({ kind: "idle" });
  const [dragging, setDragging] = useState(false);
  const [samples, setSamples] = useState<SampleInfo[]>([]);
  const [sampleId, setSampleId] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    listSamples(controller.signal)
      .then(setSamples)
      .catch(() => setSamples([]));
    return () => controller.abort();
  }, []);

  const loadSample = async () => {
    if (!sampleId) return;
    try {
      const sample = await fetchSample(sampleId);
      if (inputRef.current) inputRef.current.value = "";
      setFile(sample);
      setState({ kind: "idle" });
    } catch (error) {
      setState({ kind: "error", message: error instanceof ApiError ? error.message : "The sample could not be loaded." });
    }
  };

  const choose = (selected: File | undefined) => {
    if (!selected) return;
    const problem = validateFile(selected);
    setFile(problem ? null : selected);
    setState(problem ? { kind: "error", message: problem } : { kind: "idle" });
  };

  const onInputChange = (event: ChangeEvent<HTMLInputElement>) => choose(event.target.files?.[0]);

  const onDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setDragging(false);
    if (state.kind !== "processing") choose(event.dataTransfer.files[0]);
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!file) return;
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setState({ kind: "processing" });
    try {
      const result = await extractReport(file, controller.signal);
      setState({ kind: "success", result });
    } catch (error) {
      if (controller.signal.aborted) return;
      const message = error instanceof ApiError ? error.message : "Something went wrong while processing the file.";
      setState({ kind: "error", message });
    }
  };

  const reset = () => {
    controllerRef.current?.abort();
    setFile(null);
    setSampleId("");
    setState({ kind: "idle" });
    if (inputRef.current) inputRef.current.value = "";
  };

  const processing = state.kind === "processing";

  return (
    <section aria-labelledby="upload-heading" className="space-y-6">
      <div>
        <h2 id="upload-heading" className="text-xl font-semibold">
          Analyse a report
        </h2>
        <p className="mt-1 text-sm text-muted">
          Upload a digitally generated PDF lab report. The file is processed in memory and is not stored.
        </p>
      </div>

      <form onSubmit={onSubmit} className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
        <input
          ref={inputRef}
          id="report-file"
          type="file"
          accept="application/pdf,.pdf"
          onChange={onInputChange}
          disabled={processing}
          className="peer sr-only"
        />
        <label
          htmlFor="report-file"
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-4 py-10 text-center transition-colors peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-brand peer-disabled:cursor-not-allowed peer-disabled:opacity-60 ${
            dragging ? "border-brand bg-brand-soft" : "border-border hover:bg-background"
          }`}
        >
          <span className="font-medium">{file ? file.name : "Choose a PDF or drag it here"}</span>
          <span className="text-sm text-muted">
            {file ? `${(file.size / 1024).toFixed(0)} KB · click to choose a different file` : "PDF only"}
          </span>
        </label>

        {samples.length > 0 && (
          <div className="mt-4 flex flex-wrap items-end gap-2 text-sm">
            <label htmlFor="sample-select" className="w-full text-muted sm:w-auto">
              No report to hand? Try a synthetic sample:
            </label>
            <select
              id="sample-select"
              value={sampleId}
              onChange={(event) => setSampleId(event.target.value)}
              disabled={processing}
              className="min-w-0 flex-1 rounded-lg border border-border bg-surface px-2 py-1.5 focus-visible:outline-2 focus-visible:outline-brand sm:flex-none"
            >
              <option value="">Choose a sample…</option>
              {samples.map((sample) => (
                <option key={sample.id} value={sample.id} title={sample.description}>
                  {sample.title}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={loadSample}
              disabled={!sampleId || processing}
              className="rounded-lg border border-border px-3 py-1.5 font-medium hover:bg-background focus-visible:outline-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-50"
            >
              Use sample
            </button>
            {sampleId && (
              <p className="w-full text-xs text-muted">{samples.find((s) => s.id === sampleId)?.description}</p>
            )}
          </div>
        )}

        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="submit"
            disabled={!file || processing}
            className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-50 dark:text-background"
          >
            {processing ? "Processing…" : "Extract report"}
          </button>
          {(file || state.kind !== "idle") && (
            <button
              type="button"
              onClick={reset}
              className="rounded-lg border border-border px-4 py-2 text-sm font-medium transition-colors hover:bg-background focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
            >
              Clear report
            </button>
          )}
        </div>

        <div role="status" aria-live="polite" className="mt-4 text-sm">
          {processing && (
            <p className="flex items-center gap-2 text-muted">
              <span aria-hidden="true" className="size-2.5 animate-pulse rounded-full bg-brand" />
              Uploading and extracting text…
            </p>
          )}
          {state.kind === "error" && (
            <p role="alert" className="rounded-lg border border-danger/40 px-3 py-2 text-danger">
              {state.message}
            </p>
          )}
        </div>
      </form>

      {state.kind === "success" && file && <ExtractionResults result={state.result} file={file} />}
    </section>
  );
}
