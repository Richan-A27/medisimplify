"use client";

import { useEffect, useRef, useState, type ChangeEvent, type DragEvent, type FormEvent } from "react";

import { ExtractionResults } from "@/components/ExtractionResults";
import { FileIcon, UploadIcon } from "@/components/icons";
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
  const selectedSample = samples.find((s) => s.id === sampleId);

  return (
    <section id="analyse" aria-labelledby="upload-heading" className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 id="upload-heading" className="text-2xl font-semibold tracking-tight">
            Analyse a report
          </h2>
          <p className="mt-1 text-sm text-muted">
            Upload a digitally generated PDF lab report. The file is processed in memory and is not stored.
          </p>
        </div>
      </div>

      <form onSubmit={onSubmit} className="card p-5 sm:p-6">
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
          <div>
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
              className={`flex h-full min-h-44 cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-4 py-8 text-center transition-colors peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-brand peer-disabled:cursor-not-allowed peer-disabled:opacity-60 ${
                dragging ? "border-brand bg-brand-soft" : file ? "border-brand/40 bg-brand-soft/50" : "border-border bg-subtle hover:border-brand/40"
              }`}
            >
              <span className="flex size-11 items-center justify-center rounded-full bg-surface text-brand shadow-sm ring-1 ring-border">
                {file ? <FileIcon className="size-5" /> : <UploadIcon className="size-5" />}
              </span>
              <span className="break-all font-medium">{file ? file.name : "Choose a PDF or drag it here"}</span>
              <span className="text-sm text-muted">
                {file ? `${(file.size / 1024).toFixed(0)} KB · click to choose a different file` : "PDF only"}
              </span>
            </label>
          </div>

          <div className="flex flex-col gap-4 rounded-xl bg-subtle p-4 ring-1 ring-border">
            {samples.length > 0 && (
              <div className="space-y-2 text-sm">
                <label htmlFor="sample-select" className="block font-medium">
                  No report to hand? Try a synthetic sample:
                </label>
                <div className="flex flex-col gap-2 sm:flex-row lg:flex-col">
                  <select
                    id="sample-select"
                    value={sampleId}
                    onChange={(event) => setSampleId(event.target.value)}
                    disabled={processing}
                    className="min-w-0 flex-1 rounded-lg border border-border bg-surface px-2.5 py-2 focus-visible:outline-2 focus-visible:outline-brand"
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
                    className="rounded-lg border border-border bg-surface px-3 py-2 font-medium hover:bg-background focus-visible:outline-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Use sample
                  </button>
                </div>
                <p className="min-h-4 text-xs text-muted">
                  {selectedSample ? selectedSample.description : "All samples are fictional."}
                </p>
              </div>
            )}

            <div className="mt-auto flex flex-col gap-2">
              <button
                type="submit"
                disabled={!file || processing}
                className="rounded-lg bg-brand px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-50"
              >
                {processing ? "Processing…" : "Extract report"}
              </button>
              {(file || state.kind !== "idle") && (
                <button
                  type="button"
                  onClick={reset}
                  className="rounded-lg border border-border bg-surface px-4 py-2.5 text-sm font-medium transition-colors hover:bg-background focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                >
                  Clear report
                </button>
              )}
            </div>
          </div>
        </div>

        <div role="status" aria-live="polite" className="text-sm empty:hidden">
          {processing && (
            <p className="mt-4 flex items-center gap-2 text-muted">
              <span aria-hidden="true" className="size-2.5 animate-pulse rounded-full bg-brand" />
              Uploading and extracting text…
            </p>
          )}
          {state.kind === "error" && (
            <p role="alert" className="mt-4 rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-danger">
              {state.message}
            </p>
          )}
        </div>
      </form>

      {state.kind === "success" && file && <ExtractionResults result={state.result} file={file} />}
    </section>
  );
}
