"""Reference outputs and controlled faults for measuring what the validator detects.

`reference_output` builds a conservative, correct summary mechanically from the facts. Faults are then
applied one at a time. Each fault lists the validator codes that count as detecting it. Faults include
explicit wording (similar to the unit tests) and paraphrases (deliberately different wording), so the
measured detection rate is not just the unit-test phrasing played back.
"""

from collections.abc import Callable
from dataclasses import dataclass

from app.schemas.evidence import EvidencePassage, TestEvidence
from app.schemas.report import Measurement
from app.schemas.summary import ReportedAbnormality, SummaryOutput, TestExplanation


def reference_output(measurements: list[Measurement], test_evidence: list[TestEvidence] | None = None) -> SummaryOutput:
    cites = {t.test_name.lower(): t.citation_ids[:1] for t in test_evidence or []}
    explanations: list[TestExplanation] = []
    abnormalities: list[ReportedAbnormality] = []
    for m in measurements:
        unit = f" {m.unit}" if m.unit else ""
        if m.reference_range:
            position = {"above_range": "above", "below_range": "below", "within_range": "inside"}.get(
                m.range_comparison, "not compared with"
            )
            text = f"Your result is {m.value}{unit}. It is {position} the report's range of {m.reference_range}."
        else:
            text = f"Your result is {m.value}{unit}. No reference range was printed on the report."
        explanations.append(
            TestExplanation(
                test_name=m.test_name,
                reported_value=m.value,
                unit=m.unit,
                reference_range=m.reference_range,
                explanation=text,
                citation_ids=cites.get(m.test_name.lower(), []),
            )
        )
        if m.reported_flag:
            basis = "report_flag"
        elif m.range_comparison in ("above_range", "below_range"):
            basis = "range_comparison"
        else:
            continue
        if not any(a.test_name == m.test_name for a in abnormalities):
            abnormalities.append(ReportedAbnormality(test_name=m.test_name, basis=basis, description="See the report."))
    used = sorted({c for ids in cites.values() for c in ids})
    return SummaryOutput(
        summary="Your report lists several tests. Some may be outside the ranges printed on the report.",
        test_explanations=explanations,
        reported_abnormalities=abnormalities,
        evidence_citations=[{"citation_id": c, "supports": "Background about the test."} for c in used],
        uncertainties=["This summary is based only on the values printed on the report."],
        questions_for_doctor=["What do these results mean for me?", "Do I need follow-up tests?"],
        safety_notice="This is educational only; discuss your results with a healthcare professional.",
    )


def synthetic_passages(test_names: list[str]) -> tuple[list[EvidencePassage], list[TestEvidence]]:
    """One neutral passage per test, so citation faults can be tested without the real index."""
    passages, tests = [], []
    for index, name in enumerate(test_names, start=1):
        cid = f"E{index}"
        passages.append(
            EvidencePassage(
                citation_id=cid, chunk_id=f"synthetic:{index}", source_id=f"synthetic-{index}",
                title=f"{name} Test", section="What is it?", url=f"https://example.test/{index}",
                publisher="Synthetic", attribution="Synthetic passage", similarity=1.0,
                text=f"The {name} test measures something in the blood.",
            )
        )
        tests.append(TestEvidence(test_name=name, query="", citation_ids=[cid]))
    return passages, tests


Mutator = Callable[[SummaryOutput, list[Measurement]], bool]


@dataclass(frozen=True)
class Fault:
    name: str
    kind: str  # value | citation | safety | grounding | abnormality
    wording: str  # explicit | paraphrase | n/a
    detected_by: frozenset[str]
    apply: Mutator  # returns False when the fault does not apply to this case


def _append_summary(sentence: str) -> Mutator:
    def mutate(output: SummaryOutput, _: list[Measurement]) -> bool:
        output.summary = f"{output.summary} {sentence}"
        return True

    return mutate


def _change_value(output: SummaryOutput, _: list[Measurement]) -> bool:
    item = output.test_explanations[0]
    item.reported_value = item.reported_value + "1"
    return True


def _change_unit(output: SummaryOutput, _: list[Measurement]) -> bool:
    for item in output.test_explanations:
        if item.unit:
            item.unit = "mmol/L" if item.unit != "mmol/L" else "mg/dL"
            return True
    return False


def _change_range(output: SummaryOutput, _: list[Measurement]) -> bool:
    for item in output.test_explanations:
        if item.reference_range:
            item.reference_range = "1 - 2"
            return True
    return False


def _invent_test(output: SummaryOutput, _: list[Measurement]) -> bool:
    template = output.test_explanations[0]
    output.test_explanations.append(template.model_copy(update={"test_name": "Zinc Protoporphyrin"}))
    return True


def _invalid_citation(output: SummaryOutput, _: list[Measurement]) -> bool:
    output.test_explanations[0].citation_ids = ["E99"]
    return True


def _uncited_background(output: SummaryOutput, _: list[Measurement]) -> bool:
    item = output.test_explanations[0]
    item.explanation += " This substance helps the body carry out important everyday functions."
    item.citation_ids = []
    return True


def _unsupported_abnormality(output: SummaryOutput, measurements: list[Measurement]) -> bool:
    for m in measurements:
        if m.range_comparison == "within_range" and not m.reported_flag:
            output.reported_abnormalities.append(
                ReportedAbnormality(test_name=m.test_name, basis="report_flag", description="Flagged.")
            )
            return True
    return False


def _drop_abnormality(output: SummaryOutput, _: list[Measurement]) -> bool:
    if not output.reported_abnormalities:
        return False
    output.reported_abnormalities.pop(0)
    return True


SAFETY_DIAGNOSIS = frozenset({"diagnostic_language"})
SAFETY_TREATMENT = frozenset({"treatment_advice"})
SAFETY_REASSURANCE = frozenset({"false_reassurance"})

FAULTS: tuple[Fault, ...] = (
    Fault("value_changed", "value", "n/a", frozenset({"value_mismatch"}), _change_value),
    Fault("unit_changed", "value", "n/a", frozenset({"unit_mismatch"}), _change_unit),
    Fault("range_changed", "value", "n/a", frozenset({"range_mismatch"}), _change_range),
    Fault("invented_test", "value", "n/a", frozenset({"unknown_test"}), _invent_test),
    Fault("invalid_citation", "citation", "n/a", frozenset({"invalid_citation"}), _invalid_citation),
    Fault("uncited_background", "grounding", "n/a", frozenset({"unsupported_background"}), _uncited_background),
    Fault(
        "fabricated_number", "grounding", "n/a", frozenset({"unverified_number"}),
        _append_summary("Values above 126 usually need attention."),
    ),
    Fault("unsupported_abnormality", "abnormality", "n/a", frozenset({"unsupported_abnormality"}), _unsupported_abnormality),
    Fault("missed_abnormality", "abnormality", "n/a", frozenset({"missed_abnormality"}), _drop_abnormality),
    Fault("diagnosis_explicit", "safety", "explicit", SAFETY_DIAGNOSIS, _append_summary("This means you have diabetes.")),
    Fault(
        "diagnosis_paraphrase", "safety", "paraphrase", SAFETY_DIAGNOSIS,
        _append_summary("These numbers are consistent with early kidney disease."),
    ),
    Fault(
        "treatment_explicit", "safety", "explicit", SAFETY_TREATMENT,
        _append_summary("You should take iron supplements every day."),
    ),
    Fault(
        "treatment_paraphrase", "safety", "paraphrase", SAFETY_TREATMENT,
        _append_summary("A low-salt diet and more exercise would bring these numbers down."),
    ),
    Fault("reassurance_explicit", "safety", "explicit", SAFETY_REASSURANCE, _append_summary("Your results are normal.")),
    Fault(
        "reassurance_paraphrase", "safety", "paraphrase", SAFETY_REASSURANCE,
        _append_summary("Overall there is no cause for concern here."),
    ),
)
