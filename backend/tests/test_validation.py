from collections.abc import Callable

import pytest

from app.safety.validation import validate_summary
from app.schemas.report import Measurement
from app.schemas.summary import ReportedAbnormality, SummaryOutput, ValidationReport
from app.services.pdf_extraction import PageText
from app.services.report_parser import parse_measurements
from scripts.synthetic_reports import REPORTS
from tests.llm_fakes import passages_for, safe_output

MEASUREMENTS = parse_measurements([PageText(1, "\n".join(REPORTS["metabolic_abnormal"]))])
NAMES = [m.test_name for m in MEASUREMENTS]
PASSAGES, TEST_EVIDENCE = passages_for(NAMES)


def run(mutate: Callable[[SummaryOutput], None] | None = None, strategy: str = "rag") -> ValidationReport:
    output = safe_output(MEASUREMENTS, TEST_EVIDENCE if strategy == "rag" else None)
    if mutate:
        mutate(output)
    evidence = PASSAGES if strategy == "rag" else []
    tests = TEST_EVIDENCE if strategy == "rag" else []
    return validate_summary(output, MEASUREMENTS, strategy, evidence, tests)  # type: ignore[arg-type]


def codes(report: ValidationReport, severity: str | None = None) -> set[str]:
    return {i.code for i in report.issues if severity is None or i.severity == severity}


@pytest.mark.parametrize("strategy", ["zero_shot", "few_shot", "rag"])
def test_faithful_output_passes(strategy: str) -> None:
    report = run(strategy=strategy)

    assert report.status == "passed", report.issues
    assert "safety_language" in report.checks_run


def test_changed_value_fails() -> None:
    def mutate(o: SummaryOutput) -> None:
        o.test_explanations[0].reported_value = "182"

    assert "value_mismatch" in codes(run(mutate), "error")


def test_changed_unit_and_range_fail() -> None:
    def mutate(o: SummaryOutput) -> None:
        o.test_explanations[1].unit = "mmol/L"
        o.test_explanations[2].reference_range = "40 - 60"

    assert {"unit_mismatch", "range_mismatch"} <= codes(run(mutate), "error")


def test_invented_test_fails() -> None:
    def mutate(o: SummaryOutput) -> None:
        extra = o.test_explanations[0].model_copy(update={"test_name": "Ferritin"})
        o.test_explanations.append(extra)

    assert "unknown_test" in codes(run(mutate), "error")


def test_citation_to_unretrieved_passage_fails() -> None:
    def mutate(o: SummaryOutput) -> None:
        o.test_explanations[0].citation_ids = ["E99"]

    assert "invalid_citation" in codes(run(mutate), "error")


def test_any_citation_without_rag_fails() -> None:
    def mutate(o: SummaryOutput) -> None:
        o.test_explanations[0].citation_ids = ["E1"]

    assert "invalid_citation" in codes(run(mutate, strategy="few_shot"), "error")


def test_citation_tokens_in_text_are_checked() -> None:
    def mutate(o: SummaryOutput) -> None:
        o.summary += " Glucose provides energy [E42]."

    assert "invalid_citation" in codes(run(mutate), "error")


def test_citing_another_tests_passage_warns() -> None:
    def mutate(o: SummaryOutput) -> None:
        o.test_explanations[0].citation_ids = ["E2"]

    assert "citation_not_for_test" in codes(run(mutate), "warning")


def test_uncited_background_is_flagged_as_unsupported() -> None:
    def mutate(o: SummaryOutput) -> None:
        o.test_explanations[3].explanation += " Potassium helps your muscles and nerves work."
        o.test_explanations[3].citation_ids = []

    report = run(mutate)
    assert "unsupported_background" in codes(report, "warning")
    assert report.status == "passed_with_warnings"


def test_number_not_in_report_or_sources_warns() -> None:
    def mutate(o: SummaryOutput) -> None:
        o.summary += " Levels above 126 are concerning."

    assert "unverified_number" in codes(run(mutate), "warning")


def test_numbers_from_report_and_small_counts_are_allowed() -> None:
    def mutate(o: SummaryOutput) -> None:
        o.summary = "Your report lists 6 tests. Glucose is 128 mg/dL against a range of 70 - 99.0."

    assert "unverified_number" not in codes(run(mutate))


def test_abnormality_not_supported_by_report_fails() -> None:
    def mutate(o: SummaryOutput) -> None:
        o.reported_abnormalities.append(ReportedAbnormality(test_name="Sodium", basis="report_flag", description="Low."))

    assert "unsupported_abnormality" in codes(run(mutate), "error")


def test_missed_abnormality_warns() -> None:
    def mutate(o: SummaryOutput) -> None:
        o.reported_abnormalities = [a for a in o.reported_abnormalities if a.test_name != "HbA1c"]

    assert "missed_abnormality" in codes(run(mutate), "warning")


def test_wrong_abnormality_basis_warns() -> None:
    def mutate(o: SummaryOutput) -> None:
        for a in o.reported_abnormalities:
            if a.test_name == "Glucose, Fasting":
                a.basis = "range_comparison"

    assert "abnormality_basis_mismatch" in codes(run(mutate), "warning")


@pytest.mark.parametrize(
    ("sentence", "code"),
    [
        ("This means you have diabetes.", "diagnostic_language"),
        ("You likely have hypokalemia.", "diagnostic_language"),
        ("You are at risk for heart disease.", "diagnostic_language"),
        ("You should take potassium supplements.", "treatment_advice"),
        ("Start taking 20 mg of a statin daily.", "treatment_advice"),
        ("Your results are normal.", "false_reassurance"),
        ("You are perfectly healthy.", "false_reassurance"),
        ("There is nothing to worry about.", "false_reassurance"),
    ],
)
def test_unsafe_language_fails(sentence: str, code: str) -> None:
    def mutate(o: SummaryOutput) -> None:
        o.summary += " " + sentence

    report = run(mutate)
    assert code in codes(report, "error")
    assert report.status == "failed"


@pytest.mark.parametrize(
    "sentence",
    [
        "Your result is inside the normal range printed on the report.",
        "Glucose is measured in mg/dL.",
        "Ask your doctor whether you need follow-up tests.",
        "You may need to fast before some blood tests.",
    ],
)
def test_safe_sentences_are_not_flagged(sentence: str) -> None:
    def mutate(o: SummaryOutput) -> None:
        o.summary += " " + sentence

    assert not codes(run(mutate)) & {"diagnostic_language", "treatment_advice", "false_reassurance"}


def test_treatment_wording_in_questions_is_only_a_warning() -> None:
    def mutate(o: SummaryOutput) -> None:
        o.questions_for_doctor.append("Should I take iron supplements?")

    report = run(mutate)
    assert "treatment_advice" in codes(report, "warning")
    assert "treatment_advice" not in codes(report, "error")


def test_missing_safety_notice_and_questions_warn() -> None:
    def mutate(o: SummaryOutput) -> None:
        o.safety_notice = "Generated by AI."
        o.questions_for_doctor = []

    assert {"weak_safety_notice", "no_questions"} <= codes(run(mutate), "warning")


def test_missing_explanation_warns() -> None:
    def mutate(o: SummaryOutput) -> None:
        o.test_explanations.pop()

    assert "missing_test_explanation" in codes(run(mutate), "warning")
