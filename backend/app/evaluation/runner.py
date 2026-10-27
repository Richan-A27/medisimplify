"""Evaluation runner.

Stages (each independent, each recorded with its configuration):
  extraction  parser output vs gold annotations, including expected PDF failures
  retrieval   top-1 source accuracy and abstention on tests outside the corpus
  validator   detection of controlled faults injected into correct reference outputs
  safety_language  unsafe-language detection on labelled dev and frozen held-out sentence sets
  llm         zero-shot vs few-shot vs RAG summaries with identical model settings

LLM responses are saved so a run can be re-scored later without calling the API (`replay`).
"""

import csv
import datetime as dt
import json
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import Settings
from app.evaluation.dataset import Dataset, EvalCase
from app.evaluation.metrics import (
    aggregate_summary_metrics,
    extraction_metrics,
    mean_or_none,
    prf,
    retrieval_metrics,
    summary_metrics,
)
from app.evaluation.reference import FAULTS, reference_output, synthetic_passages
from app.evaluation.safety_sets import DEV_SET, HELDOUT_SET, evaluate_safety_set
from app.prompts.builder import PromptBundle
from app.prompts.templates import PROMPT_VERSION
from app.rag.retrieval import KnowledgeBaseUnavailableError, Retriever
from app.safety.validation import validate_summary
from app.schemas.report import ExtractionResponse
from app.schemas.summary import STRATEGIES, Strategy, TokenUsage
from app.services.llm import LLMClient, LLMError, LLMResult
from app.services.pdf_extraction import PDFExtractionError, PyMuPDFTextExtractor
from app.services.report_extraction import extract_report
from app.services.summarizer import NoMeasurementsError, summarize

STAGES = ("extraction", "retrieval", "validator", "safety_language", "llm")


class RecordingLLM:
    """Wraps a client and keeps every raw response for later replay."""

    def __init__(self, inner: LLMClient) -> None:
        self.inner = inner
        self.model = inner.model
        self.last: tuple[LLMResult, str] | None = None

    def generate(self, prompt: PromptBundle) -> LLMResult:
        result = self.inner.generate(prompt)
        self.last = (result, prompt.sha256)
        return result


class ReplayLLM:
    """Serves responses saved by a previous run instead of calling the API."""

    def __init__(self, responses_dir: Path) -> None:
        self.responses_dir = responses_dir
        self.key: tuple[str, str] | None = None
        self.model = "replay"
        self.prompt_mismatches: list[str] = []

    def generate(self, prompt: PromptBundle) -> LLMResult:
        assert self.key is not None
        strategy, case_id = self.key
        path = self.responses_dir / strategy / f"{case_id}.json"
        if not path.exists():
            raise LLMError(f"No saved response for {strategy}/{case_id}.")
        saved = json.loads(path.read_text())
        if saved["prompt_sha256"] != prompt.sha256:
            self.prompt_mismatches.append(f"{strategy}/{case_id}")
        self.model = saved["model"]
        return LLMResult(
            text=saved["text"], model=saved["model"], usage=TokenUsage(**saved["usage"]), latency_ms=saved["latency_ms"]
        )


@dataclass
class RunConfig:
    stages: tuple[str, ...] = STAGES
    strategies: tuple[Strategy, ...] = STRATEGIES
    out_dir: Path | None = None
    llm_delay_seconds: float = 0.0
    human_ratings: Path | None = None
    rating_key: Path | None = None
    notes: list[str] = field(default_factory=list)


def _extract(case: EvalCase, settings: Settings) -> ExtractionResponse:
    return extract_report(
        case.pdf_bytes(), extractor=PyMuPDFTextExtractor(settings.max_pdf_pages), max_bytes=settings.max_upload_bytes
    )


def run_extraction(dataset: Dataset, settings: Settings) -> dict[str, Any]:
    per_case: dict[str, Any] = {}
    totals = {"tp": 0, "pred": 0, "gold": 0}
    error_cases = error_correct = unexpected_errors = 0
    for case in dataset.cases:
        try:
            extraction = _extract(case, settings)
        except PDFExtractionError as exc:
            correct = exc.code == case.expected_error
            per_case[case.id] = {"error": exc.code, "expected_error": case.expected_error, "error_correct": correct}
            if case.expected_error:
                error_cases += 1
                error_correct += correct
            else:
                unexpected_errors += 1
            continue
        if case.expected_error:
            error_cases += 1
            per_case[case.id] = {"error": None, "expected_error": case.expected_error, "error_correct": False}
            continue
        metrics = extraction_metrics(case, extraction.measurements, [w.code for w in extraction.warnings])
        per_case[case.id] = metrics
        totals["tp"] += metrics["exact_matches"]
        totals["pred"] += metrics["predicted_count"]
        totals["gold"] += metrics["gold_count"]
    return {
        "aggregate": {
            "measurement_micro": prf(totals["tp"], totals["pred"], totals["gold"]),
            "gold_measurements": totals["gold"],
            "failure_cases": error_cases,
            "failure_cases_with_expected_error": error_correct,
            "unexpected_errors": unexpected_errors,
        },
        "per_case": per_case,
    }


def run_retrieval(dataset: Dataset, retriever: Retriever) -> dict[str, Any]:
    per_case: dict[str, Any] = {}
    for case in dataset.cases:
        names = list(dict.fromkeys(case.expected_sources))
        if not names:
            continue
        response = retriever.retrieve_for_tests(names)
        per_case[case.id] = retrieval_metrics(case, response.tests, response.passages)
    hits = [t for c in per_case.values() for t in c["per_test"] if t["expected"]]
    abstain = [t for c in per_case.values() for t in c["per_test"] if not t["expected"]]
    return {
        "aggregate": {
            "covered_tests": len(hits),
            "top1_accuracy": sum(t["top1_correct"] for t in hits) / len(hits) if hits else None,
            "hit_rate_at_k": sum(any(s in t["expected"] for s in t["retrieved"]) for t in hits) / len(hits) if hits else None,
            "uncovered_tests": len(abstain),
            "abstention_rate": sum(t["abstained"] for t in abstain) / len(abstain) if abstain else None,
            "min_similarity": retriever.min_similarity,
            "top_k": retriever.top_k,
            "embedding_model": retriever.embedder.model_name,
        },
        "per_case": per_case,
    }


def run_validator(dataset: Dataset, settings: Settings) -> dict[str, Any]:
    per_fault: dict[str, dict[str, Any]] = {
        f.name: {"kind": f.kind, "wording": f.wording, "applicable": 0, "detected": 0, "blocked": 0, "missed_cases": []}
        for f in FAULTS
    }
    clean_cases = clean_passed = 0
    clean_issues: dict[str, list[str]] = {}
    for case in dataset.cases:
        if not case.summarizable:
            continue
        measurements = _extract(case, settings).measurements
        names = list(dict.fromkeys(m.test_name for m in measurements))
        passages, tests = synthetic_passages(names)
        clean = reference_output(measurements, tests)
        report = validate_summary(clean, measurements, "rag", passages, tests)
        clean_cases += 1
        clean_passed += report.status == "passed"
        if report.issues:
            clean_issues[case.id] = [i.code for i in report.issues]
        for fault in FAULTS:
            output = clean.model_copy(deep=True)
            if not fault.apply(output, measurements):
                continue
            result = validate_summary(output, measurements, "rag", passages, tests)
            stats = per_fault[fault.name]
            stats["applicable"] += 1
            detected = any(i.code in fault.detected_by for i in result.issues)
            stats["detected"] += detected
            stats["blocked"] += result.status == "failed"
            if not detected:
                stats["missed_cases"].append(case.id)
    for stats in per_fault.values():
        stats["detection_rate"] = stats["detected"] / stats["applicable"] if stats["applicable"] else None
    by_wording = {
        wording: mean_or_none(s["detection_rate"] for s in per_fault.values() if s["wording"] == wording)
        for wording in ("explicit", "paraphrase", "n/a")
    }
    return {
        "aggregate": {
            "clean_outputs": clean_cases,
            "clean_outputs_passed": clean_passed,
            "clean_issue_codes": clean_issues,
            "mean_detection_rate_by_wording": by_wording,
        },
        "per_fault": per_fault,
    }


def run_llm(
    dataset: Dataset,
    settings: Settings,
    llm: LLMClient,
    get_retriever: Callable[[], Retriever],
    config: RunConfig,
) -> dict[str, Any]:
    recorder = llm if isinstance(llm, ReplayLLM) else RecordingLLM(llm)
    responses_dir = config.out_dir / "responses" if config.out_dir else None
    per_strategy: dict[str, Any] = {}
    outputs: dict[str, dict[str, Any]] = {}
    first_call = True
    for strategy in config.strategies:
        rows: dict[str, Any] = {}
        for case in dataset.cases:
            if case.expected_error:
                continue
            extraction = _extract(case, settings)
            if isinstance(recorder, ReplayLLM):
                recorder.key = (strategy, case.id)
            elif not first_call and config.llm_delay_seconds:
                time.sleep(config.llm_delay_seconds)
            first_call = False
            try:
                response = summarize(extraction, strategy, recorder, get_retriever)
            except NoMeasurementsError as exc:
                rows[case.id] = {"refused": exc.code, "refusal_expected": case.expected_summary_error == exc.code}
                continue
            except (LLMError, KnowledgeBaseUnavailableError) as exc:
                rows[case.id] = {"error_code": getattr(exc, "code", "error"), "message": str(exc)}
                continue
            rows[case.id] = summary_metrics(case, response)
            outputs.setdefault(strategy, {})[case.id] = response.output.model_dump()
            if isinstance(recorder, RecordingLLM) and recorder.last and responses_dir:
                result, prompt_sha = recorder.last
                path = responses_dir / strategy / f"{case.id}.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    json.dumps(
                        {
                            "text": result.text,
                            "model": result.model,
                            "usage": result.usage.model_dump(),
                            "latency_ms": result.latency_ms,
                            "prompt_sha256": prompt_sha,
                        },
                        indent=1,
                    )
                )
        scored = [r for r in rows.values() if "refused" not in r]
        per_strategy[strategy] = {"aggregate": aggregate_summary_metrics(scored), "per_case": rows}
    result: dict[str, Any] = {"per_strategy": per_strategy}
    if isinstance(recorder, ReplayLLM):
        result["replay_prompt_mismatches"] = recorder.prompt_mismatches
    if config.out_dir and outputs:
        write_rating_sheet(outputs, config.out_dir)
    return result


def write_rating_sheet(outputs: dict[str, dict[str, Any]], out_dir: Path, seed: int = 7) -> None:
    """Blinded sheet for human raters: items are shuffled and strategy names hidden in a separate key."""
    items = [(strategy, case_id, output) for strategy, cases in outputs.items() for case_id, output in cases.items()]
    random.Random(seed).shuffle(items)
    key: dict[str, dict[str, str]] = {}
    lines = ["# Outputs to rate (strategy hidden)\n"]
    with (out_dir / "human_ratings.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["item_id", "case_id", "rater_id", "factual_accuracy_1to5", "clarity_1to5",
                         "completeness_1to5", "safe_and_appropriate_yes_no", "notes"])
        for index, (strategy, case_id, output) in enumerate(items, start=1):
            item_id = f"item-{index:03d}"
            key[item_id] = {"strategy": strategy, "case_id": case_id}
            writer.writerow([item_id, case_id, "", "", "", "", "", ""])
            lines.append(f"## {item_id} (case {case_id})\n\n```json\n{json.dumps(output, indent=1)}\n```\n")
    (out_dir / "rating_items.md").write_text("\n".join(lines))
    (out_dir / "rating_key.json").write_text(json.dumps(key, indent=1))


def aggregate_human_ratings(ratings: Path, key_path: Path) -> dict[str, Any]:
    key = json.loads(key_path.read_text())
    per_strategy: dict[str, dict[str, list[float]]] = {}
    raters: set[str] = set()
    with ratings.open() as handle:
        for row in csv.DictReader(handle):
            if not row.get("rater_id") or not row.get("factual_accuracy_1to5"):
                continue
            raters.add(row["rater_id"])
            strategy = key[row["item_id"]]["strategy"]
            bucket = per_strategy.setdefault(strategy, {"factual_accuracy": [], "clarity": [], "completeness": [], "safe": []})
            bucket["factual_accuracy"].append(float(row["factual_accuracy_1to5"]))
            bucket["clarity"].append(float(row["clarity_1to5"]))
            bucket["completeness"].append(float(row["completeness_1to5"]))
            bucket["safe"].append(1.0 if row["safe_and_appropriate_yes_no"].strip().lower() == "yes" else 0.0)
    return {
        "raters": len(raters),
        "per_strategy": {
            s: {metric: {"mean": mean_or_none(v), "n": len(v)} for metric, v in values.items()}
            for s, values in per_strategy.items()
        },
    }


def run_evaluation(
    dataset: Dataset,
    settings: Settings,
    config: RunConfig,
    *,
    llm: LLMClient | None,
    llm_unavailable_reason: str | None,
    get_retriever: Callable[[], Retriever],
) -> dict[str, Any]:
    started = dt.datetime.now(dt.UTC)
    results: dict[str, Any] = {
        "created": started.isoformat(timespec="seconds"),
        "dataset": {
            "name": dataset.name,
            "version": dataset.version,
            "cases": len(dataset.cases),
            "annotation": dataset.annotation,
        },
        "config": {
            "stages": list(config.stages),
            "strategies": list(config.strategies),
            "prompt_version": PROMPT_VERSION,
            "llm_model": getattr(llm, "model", None),
            "temperature": settings.llm_temperature,
            "seed": settings.llm_seed,
            "max_output_tokens": settings.llm_max_output_tokens,
            "embedding_model": settings.embedding_model,
            "rag_top_k": settings.rag_top_k,
            "rag_min_similarity": settings.rag_min_similarity,
        },
        "notes": config.notes,
    }
    if "extraction" in config.stages:
        results["extraction"] = run_extraction(dataset, settings)
    if "retrieval" in config.stages:
        try:
            results["retrieval"] = run_retrieval(dataset, get_retriever())
        except KnowledgeBaseUnavailableError as exc:
            results["retrieval"] = {"skipped": str(exc) or exc.message}
    if "validator" in config.stages:
        results["validator"] = run_validator(dataset, settings)
    if "safety_language" in config.stages:
        results["safety_language"] = {
            "dev": evaluate_safety_set(DEV_SET),
            "heldout": evaluate_safety_set(HELDOUT_SET),
        }
    if "llm" in config.stages:
        if llm is None:
            results["llm"] = {"skipped": llm_unavailable_reason or "No LLM configured."}
        else:
            results["llm"] = run_llm(dataset, settings, llm, get_retriever, config)
    if config.human_ratings and config.rating_key:
        results["human"] = aggregate_human_ratings(config.human_ratings, config.rating_key)
    else:
        results["human"] = {"status": "not collected"}
    return results
