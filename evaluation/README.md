# Evaluation

A reproducible evaluation of MediSimplify's four components, run on synthetic reports only.

| Stage | Question | Needs |
| --- | --- | --- |
| `extraction` | Does the parser copy test name, value, unit, range and flag exactly, and fail clearly on bad PDFs? | nothing |
| `retrieval` | Is the top passage from the right source, and does retrieval stay silent for tests outside the corpus? | built index |
| `validator` | Which controlled faults does the safety validator detect? | nothing |
| `safety_language` | How well is unsafe wording detected on a labelled development set and a frozen held-out set? | nothing |
| `llm` | How do zero-shot, few-shot and RAG-enhanced prompting compare under identical settings? | `GEMINI_API_KEY` (or `--replay`) |

## Running

From the repository root:

```bash
backend/.venv/bin/python evaluation/scripts/run_evaluation.py
```

Useful options:

- `--stages extraction retrieval validator`: offline stages only.
- `--stages llm --delay 6`: LLM stage only, pausing 6 s between calls for free-tier rate limits (3 strategies × 10 cases = 30 calls).
- `--replay evaluation/results/<run>/responses`: re-score saved model responses without calling the API.
  The run reports any case whose prompt changed since it was recorded.
- `--human-ratings <completed csv> --rating-key evaluation/results/<run>/rating_key.json`: add human judgments.
- `--run-id NAME`: output folder name (default: a timestamp).

Each run writes `evaluation/results/<run-id>/`:

- `results.json`: every metric, per case and aggregated, plus the configuration: model, temperature, seed, prompt version, embedding model and threshold.
- `report.md`: the same results as tables.
- After an LLM run:
  - `responses/`: raw model outputs (synthetic data only) for replay.
  - `human_ratings.csv`, `rating_items.md`: a blinded rating sheet in which items are shuffled and strategy names are hidden.
  - `rating_key.json`: the mapping from items back to strategies.

## Fair comparison of prompting strategies

All three strategies use the same reports, extracted facts, system instructions, JSON schema, model and generation settings (`temperature` 0.2, `seed` 42). Only these differ:

- whether the reviewed examples are included;
- whether retrieved passages are included.

Every response stores the SHA-256 of its exact prompt. Gemini does not guarantee deterministic output even with a fixed seed. Re-score saved responses with `--replay` rather than calling the API again, and report the run ID.

## Metrics

Everything below is **computed automatically** by [metrics.py](../backend/app/evaluation/metrics.py).

| Metric | Definition |
| --- | --- |
| Measurement precision / recall | Exact match on (name, value, unit, range, flag) against gold. |
| Failure handling | Expected PDF failures (scanned, encrypted) reported with the expected error code. |
| Top-1 source accuracy | The first passage retrieved for a test comes from an acceptable gold source. |
| Abstention rate | Tests outside the corpus receive no passages. |
| Fault detection rate | Share of injected faults for which the validator raised a matching issue; "blocked" = summary marked failed. |
| Value preservation | Share of gold tests whose explanation repeats value, unit and range exactly. |
| Abnormality precision / recall | Tests listed in `reported_abnormalities` vs gold abnormal tests. |
| Unsupported-claim rate | `unsupported_background` warnings per explanation (background sentences without a citation) plus `unverified_number` warnings. |
| Citation validity / relevance | Cited IDs that exist among retrieved passages / cited passages whose source is a gold source for that test. |
| Safety failures | Diagnostic, treatment or false-reassurance language flagged as errors. |
| Readability | Flesch-Kincaid grade and Flesch reading ease of summary + explanations (heuristic syllable count). |
| Latency, tokens | As reported by the API per call. |

**Human judgments** are collected separately on the blinded sheet:

- factual accuracy, clarity and completeness, each on a 1–5 scale;
- safe and appropriate: yes/no.

They are aggregated per strategy and never mixed with the automatic metrics. See [datasets/README.md](datasets/README.md) for the rating guide.

## Recorded results

- [results/2026-10-27-validator-v2/report.md](results/2026-10-27-validator-v2/report.md): current validator, including the safety-language held-out results. Live responses were re-scored with `--replay`.
- [results/2026-10-27-live-flash-lite/report.md](results/2026-10-27-live-flash-lite/report.md): all stages with live `gemini-3.5-flash-lite`. Saved responses and a blinded human-rating sheet are in the same folder.
- [results/2026-10-27-offline/report.md](results/2026-10-27-offline/report.md): offline stages only, run before an API key was available.

## Limitations

- **Small and synthetic.** 12 cases, written in the same one-line row format the parser was designed for. Perfect extraction scores here say little about real lab-report layouts.
- **Unreviewed annotations.** The gold annotations were drafted by an AI assistant and still need independent human review before results are reported.
- **The fault suite was written by the project,** so its detection rates describe those faults only. Its three paraphrase faults were later added to the safety development set, so they no longer measure generalisation.
- **Safety-language sets** ([safety_dev.json](datasets/safety_dev.json), [safety_heldout.json](datasets/safety_heldout.json)):
  - the held-out set is frozen; a test checks its SHA-256;
  - never tune against the held-out set; to extend it, add a new versioned file;
  - both sets share one author, so held-out results are likely optimistic.
- **No significance testing.** With this sample size, comparisons are descriptive only.
