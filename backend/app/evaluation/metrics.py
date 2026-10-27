"""Automatic metrics. Everything here is computed by code; human judgments are handled separately."""

import re
from collections.abc import Iterable
from statistics import mean

from app.evaluation.dataset import EvalCase, GoldMeasurement
from app.schemas.evidence import EvidencePassage
from app.schemas.report import Measurement
from app.schemas.summary import SummaryResponse

SAFETY_CODES = {"diagnostic_language", "treatment_advice", "false_reassurance"}


def prf(true_positive: int, predicted: int, actual: int) -> dict[str, float | None]:
    precision = true_positive / predicted if predicted else None
    recall = true_positive / actual if actual else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall
        else None
    )
    return {"precision": precision, "recall": recall, "f1": f1}


def mean_or_none(values: Iterable[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return mean(present) if present else None


# ---- readability (standard Flesch formulas with a heuristic syllable counter) ----

_WORD_RE = re.compile(r"[A-Za-z]+")


def count_syllables(word: str) -> int:
    word = word.lower()
    groups = re.findall(r"[aeiouy]+", word)
    count = len(groups)
    if word.endswith("e") and not word.endswith(("le", "ee")) and count > 1:
        count -= 1
    return max(count, 1)


def readability(text: str) -> dict[str, float | None]:
    words = _WORD_RE.findall(text)
    sentences = [s for s in re.split(r"[.!?]+(?:\s|$)", text) if _WORD_RE.search(s)]
    if not words or not sentences:
        return {"flesch_kincaid_grade": None, "flesch_reading_ease": None, "words": 0}
    words_per_sentence = len(words) / len(sentences)
    syllables_per_word = sum(count_syllables(w) for w in words) / len(words)
    return {
        "flesch_kincaid_grade": round(0.39 * words_per_sentence + 11.8 * syllables_per_word - 15.59, 2),
        "flesch_reading_ease": round(206.835 - 1.015 * words_per_sentence - 84.6 * syllables_per_word, 2),
        "words": len(words),
    }


# ---- extraction ----


def _as_gold(m: Measurement) -> GoldMeasurement:
    return GoldMeasurement(m.test_name, m.value, m.unit, m.reference_range, m.reported_flag)


def extraction_metrics(case: EvalCase, measurements: list[Measurement], warnings: list[str]) -> dict:
    gold = [g.key() for g in case.measurements]
    predicted = [_as_gold(m).key() for m in measurements]
    remaining = list(gold)
    exact = 0
    for key in predicted:
        if key in remaining:
            remaining.remove(key)
            exact += 1

    gold_abnormal = {name.lower() for name in case.abnormal}
    predicted_abnormal = {
        m.test_name.lower() for m in measurements if m.reported_flag or m.range_comparison in ("above_range", "below_range")
    }
    gold_ambiguous = {name.lower() for name in case.ambiguous_tests}
    predicted_ambiguous = {m.test_name.lower() for m in measurements if m.source_status == "ambiguous"}
    return {
        "measurements": prf(exact, len(predicted), len(gold)),
        "exact_matches": exact,
        "gold_count": len(gold),
        "predicted_count": len(predicted),
        "missed": [k[0] for k in remaining],
        "abnormal_candidates": prf(len(gold_abnormal & predicted_abnormal), len(predicted_abnormal), len(gold_abnormal)),
        "ambiguity": prf(len(gold_ambiguous & predicted_ambiguous), len(predicted_ambiguous), len(gold_ambiguous)),
        "expected_warnings_present": all(code in warnings for code in case.expected_warnings),
    }


# ---- retrieval ----


def retrieval_metrics(case: EvalCase, response_tests: list, passages: list[EvidencePassage]) -> dict:
    by_id = {p.citation_id: p for p in passages}
    top1_hits, top1_total, abstained, abstain_total, any_relevant = 0, 0, 0, 0, 0
    per_test = []
    for test in response_tests:
        expected = case.expected_sources.get(test.test_name)
        if expected is None:
            continue
        sources = [by_id[c].source_id for c in test.citation_ids]
        if expected:
            top1_total += 1
            hit = bool(sources) and sources[0] in expected
            top1_hits += hit
            any_relevant += any(s in expected for s in sources)
            per_test.append({"test": test.test_name, "expected": expected, "retrieved": sources, "top1_correct": hit})
        else:
            abstain_total += 1
            abstained += not sources
            per_test.append({"test": test.test_name, "expected": [], "retrieved": sources, "abstained": not sources})
    return {
        "top1_accuracy": top1_hits / top1_total if top1_total else None,
        "hit_rate_at_k": any_relevant / top1_total if top1_total else None,
        "abstention_rate": abstained / abstain_total if abstain_total else None,
        "covered_tests": top1_total,
        "uncovered_tests": abstain_total,
        "per_test": per_test,
    }


# ---- LLM summaries ----


def summary_metrics(case: EvalCase, response: SummaryResponse) -> dict:
    output = response.output
    issues = response.validation.issues
    codes = [i.code for i in issues]

    gold = {g.test_name.lower(): g for g in case.measurements}
    explained = {e.test_name.lower(): e for e in output.test_explanations}
    preserved = 0
    for name, g in gold.items():
        e = explained.get(name)
        if e and e.reported_value == g.value and e.unit == g.unit and e.reference_range == g.reference_range:
            preserved += 1
    # Duplicate gold names (conflicting values) can only be matched once per name.
    gold_names = len(gold)

    gold_abnormal = {k.lower(): v for k, v in case.abnormal.items()}
    listed = {a.test_name.lower(): a.basis for a in output.reported_abnormalities}
    abnormal_tp = len(set(listed) & set(gold_abnormal))
    basis_correct = sum(1 for k, v in listed.items() if gold_abnormal.get(k) == v)

    passages = {p.citation_id: p for p in response.evidence}
    cited = [(e.test_name, c) for e in output.test_explanations for c in e.citation_ids]
    valid = [(t, c) for t, c in cited if c in passages]
    relevant = [
        (t, c) for t, c in valid if passages[c].source_id in case.expected_sources.get(t, [])
    ]
    explanation_count = len(output.test_explanations) or 1
    text = " ".join([output.summary] + [e.explanation for e in output.test_explanations])

    return {
        "validation_status": response.validation.status,
        "errors": sum(1 for i in issues if i.severity == "error"),
        "warnings": sum(1 for i in issues if i.severity == "warning"),
        "issue_codes": sorted(set(codes)),
        "test_coverage": len(set(explained) & set(gold)) / gold_names if gold_names else None,
        "value_preservation": preserved / gold_names if gold_names else None,
        "value_errors": sum(codes.count(c) for c in ("value_mismatch", "unit_mismatch", "range_mismatch", "unknown_test")),
        "abnormalities": prf(abnormal_tp, len(listed), len(gold_abnormal)),
        "abnormality_basis_accuracy": basis_correct / len(listed) if listed else None,
        "unsupported_background_per_explanation": codes.count("unsupported_background") / explanation_count,
        "unverified_numbers": codes.count("unverified_number"),
        "citations": len(cited),
        "citation_validity": len(valid) / len(cited) if cited else None,
        "citation_relevance": len(relevant) / len(valid) if valid else None,
        "safety_failures": sum(1 for i in issues if i.code in SAFETY_CODES and i.severity == "error"),
        "readability": readability(text),
        "latency_ms": response.latency_ms,
        "prompt_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.output_tokens,
    }


def aggregate_summary_metrics(rows: list[dict]) -> dict:
    ok = [r for r in rows if "error_code" not in r]
    get = lambda key: [r[key] for r in ok]  # noqa: E731
    return {
        "cases": len(rows),
        "completed": len(ok),
        "llm_errors": sorted({r["error_code"] for r in rows if "error_code" in r}),
        "status_counts": {s: sum(1 for r in ok if r["validation_status"] == s) for s in ("passed", "passed_with_warnings", "failed")},
        "mean_value_preservation": mean_or_none(get("value_preservation")),
        "mean_test_coverage": mean_or_none(get("test_coverage")),
        "total_value_errors": sum(get("value_errors")),
        "mean_abnormality_recall": mean_or_none(r["abnormalities"]["recall"] for r in ok),
        "mean_abnormality_precision": mean_or_none(r["abnormalities"]["precision"] for r in ok),
        "mean_unsupported_background_per_explanation": mean_or_none(get("unsupported_background_per_explanation")),
        "total_unverified_numbers": sum(get("unverified_numbers")),
        "mean_citation_validity": mean_or_none(get("citation_validity")),
        "mean_citation_relevance": mean_or_none(get("citation_relevance")),
        "total_safety_failures": sum(get("safety_failures")),
        "mean_fk_grade": mean_or_none(r["readability"]["flesch_kincaid_grade"] for r in ok),
        "mean_reading_ease": mean_or_none(r["readability"]["flesch_reading_ease"] for r in ok),
        "mean_latency_ms": mean_or_none(get("latency_ms")),
        "mean_prompt_tokens": mean_or_none(get("prompt_tokens")),
        "mean_output_tokens": mean_or_none(get("output_tokens")),
    }
