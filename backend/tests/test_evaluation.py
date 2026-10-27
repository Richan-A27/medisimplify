import csv
import json
from dataclasses import replace
from pathlib import Path

import pytest

from app.evaluation.dataset import load_dataset
from app.evaluation.metrics import count_syllables, prf, readability
from app.evaluation.reference import FAULTS
from app.evaluation.report import render_report
from app.evaluation.runner import ReplayLLM, RunConfig, aggregate_human_ratings, run_evaluation
from app.rag.ingest import ingest
from app.rag.retrieval import KnowledgeBaseUnavailableError, Retriever
from app.rag.store import VectorStore
from app.services.llm import LLMQuotaError, LLMTimeoutError
from tests.conftest import make_settings
from tests.llm_fakes import FakeLLM
from tests.rag_fakes import SAMPLE_DOCUMENTS, HashingEmbedder, write_corpus

DATASET = load_dataset()
SETTINGS = make_settings()


def test_dataset_covers_required_categories() -> None:
    categories = {c.category for c in DATASET.cases}

    assert {
        "normal_values",
        "abnormal_values",
        "missing_reference_ranges",
        "conflicting_or_ambiguous",
        "prompt_injection",
        "missing_rag_evidence",
        "no_measurements",
        "pdf_extraction_failure",
    } <= categories
    assert DATASET.annotation["review_status"]


def test_gold_annotations_appear_verbatim_in_their_reports() -> None:
    for case in DATASET.cases:
        text = "\n".join(case.report_lines)
        for m in case.measurements:
            line = next((l for l in case.report_lines if l.startswith(m.test_name + " ")), None)
            assert line, (case.id, m.test_name)
            for part in (m.value, m.unit, m.reference_range, m.reported_flag):
                if part:
                    assert part in text, (case.id, m.test_name, part)
        assert set(case.abnormal) <= {m.test_name for m in case.measurements}
        assert set(case.expected_sources) <= {m.test_name for m in case.measurements}


def test_prf_and_readability() -> None:
    assert prf(3, 4, 6) == {"precision": 0.75, "recall": 0.5, "f1": 0.6}
    assert prf(0, 0, 0) == {"precision": None, "recall": None, "f1": None}
    assert [count_syllables(w) for w in ("cat", "table", "hemoglobin", "the")] == [1, 2, 4, 1]
    simple = readability("The cat sat. The dog ran.")
    hard = readability("Hemoglobin concentration demonstrates considerable physiological variability.")
    assert simple["flesch_kincaid_grade"] < hard["flesch_kincaid_grade"]
    assert readability("")["flesch_kincaid_grade"] is None


def test_faults_have_unique_names() -> None:
    assert len({f.name for f in FAULTS}) == len(FAULTS)


@pytest.fixture
def retriever(tmp_path: Path) -> Retriever:
    write_corpus(tmp_path / "sources", SAMPLE_DOCUMENTS)
    store = VectorStore(tmp_path / "index")
    ingest(tmp_path / "sources", store, HashingEmbedder(), max_words=60, overlap_words=10)
    return Retriever(store, HashingEmbedder(), top_k=2, min_similarity=0.2)


def small_dataset():  # noqa: ANN201
    keep = {"metabolic_abnormal", "no_results", "scanned_report", "prompt_injection"}
    return replace(DATASET, cases=[c for c in DATASET.cases if c.id in keep])


def test_offline_stages_produce_real_metrics(retriever: Retriever) -> None:
    results = run_evaluation(
        DATASET,
        SETTINGS,
        RunConfig(stages=("extraction", "retrieval", "validator", "llm")),
        llm=None,
        llm_unavailable_reason="no key",
        get_retriever=lambda: retriever,
    )

    extraction = results["extraction"]["aggregate"]
    assert extraction["failure_cases"] == 2
    assert extraction["failure_cases_with_expected_error"] == 2
    assert extraction["unexpected_errors"] == 0
    assert extraction["measurement_micro"]["recall"] is not None
    assert results["retrieval"]["aggregate"]["covered_tests"] > 0
    validator = results["validator"]
    assert validator["per_fault"]["value_changed"]["detection_rate"] == 1.0
    assert validator["per_fault"]["invalid_citation"]["detection_rate"] == 1.0
    assert validator["aggregate"]["clean_outputs_passed"] == validator["aggregate"]["clean_outputs"]
    assert results["llm"] == {"skipped": "no key"}
    assert results["human"] == {"status": "not collected"}
    report = render_report(results)
    assert "**Not run.** no key" in report
    assert "no statistical significance is claimed" in report


def test_missing_index_skips_retrieval_stage() -> None:
    def unavailable() -> Retriever:
        raise KnowledgeBaseUnavailableError()

    results = run_evaluation(
        small_dataset(), SETTINGS, RunConfig(stages=("retrieval",)), llm=None, llm_unavailable_reason=None,
        get_retriever=unavailable,
    )

    assert "skipped" in results["retrieval"]


def test_llm_stage_compares_strategies_and_supports_replay(tmp_path: Path, retriever: Retriever) -> None:
    config = RunConfig(stages=("llm",), out_dir=tmp_path)

    first = run_evaluation(small_dataset(), SETTINGS, config, llm=FakeLLM(), llm_unavailable_reason=None,
                           get_retriever=lambda: retriever)

    per_strategy = first["llm"]["per_strategy"]
    assert set(per_strategy) == {"zero_shot", "few_shot", "rag"}
    for strategy, data in per_strategy.items():
        assert data["per_case"]["no_results"] == {"refused": "no_measurements", "refusal_expected": True}
        assert "scanned_report" not in data["per_case"]
        agg = data["aggregate"]
        assert agg["completed"] == 2
        assert agg["mean_value_preservation"] == 1.0
        assert agg["total_safety_failures"] == 0
    assert per_strategy["rag"]["aggregate"]["mean_citation_validity"] in (1.0, None)
    assert (tmp_path / "responses" / "rag" / "metabolic_abnormal.json").exists()
    assert (tmp_path / "human_ratings.csv").exists()
    key = json.loads((tmp_path / "rating_key.json").read_text())
    assert len(key) == 6 and all(set(v) == {"strategy", "case_id"} for v in key.values())
    assert "zero_shot" not in (tmp_path / "rating_items.md").read_text()  # blinded

    replayed = run_evaluation(
        small_dataset(), SETTINGS, RunConfig(stages=("llm",)),
        llm=ReplayLLM(tmp_path / "responses"), llm_unavailable_reason=None, get_retriever=lambda: retriever,
    )

    assert replayed["llm"]["replay_prompt_mismatches"] == []
    for strategy in per_strategy:
        assert replayed["llm"]["per_strategy"][strategy]["per_case"] == per_strategy[strategy]["per_case"]


@pytest.mark.parametrize(("error", "code"), [(LLMQuotaError(), "llm_quota_exceeded"), (LLMTimeoutError(), "llm_timeout")])
def test_llm_errors_are_recorded_not_fatal(error: Exception, code: str, retriever: Retriever) -> None:
    results = run_evaluation(
        small_dataset(), SETTINGS, RunConfig(stages=("llm",), strategies=("zero_shot",)),
        llm=FakeLLM(error=error), llm_unavailable_reason=None, get_retriever=lambda: retriever,  # type: ignore[arg-type]
    )

    agg = results["llm"]["per_strategy"]["zero_shot"]["aggregate"]
    assert agg["llm_errors"] == [code]
    assert agg["completed"] == 0


def test_human_ratings_are_aggregated_per_hidden_strategy(tmp_path: Path) -> None:
    (tmp_path / "key.json").write_text(json.dumps({
        "item-001": {"strategy": "rag", "case_id": "a"},
        "item-002": {"strategy": "zero_shot", "case_id": "a"},
    }))
    with (tmp_path / "ratings.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["item_id", "case_id", "rater_id", "factual_accuracy_1to5", "clarity_1to5",
                         "completeness_1to5", "safe_and_appropriate_yes_no", "notes"])
        writer.writerow(["item-001", "a", "r1", "5", "4", "4", "yes", ""])
        writer.writerow(["item-002", "a", "r1", "3", "4", "2", "no", ""])
        writer.writerow(["item-001", "a", "r2", "4", "4", "5", "yes", ""])
        writer.writerow(["item-002", "a", "", "", "", "", "", "unrated row is ignored"])

    human = aggregate_human_ratings(tmp_path / "ratings.csv", tmp_path / "key.json")

    assert human["raters"] == 2
    assert human["per_strategy"]["rag"]["factual_accuracy"] == {"mean": 4.5, "n": 2}
    assert human["per_strategy"]["zero_shot"]["safe"] == {"mean": 0.0, "n": 1}
