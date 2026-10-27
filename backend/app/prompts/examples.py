"""Reviewed few-shot examples.

The example reports are synthetic and use different values from the evaluation reports. Reference
passages are verbatim excerpts from the MedlinePlus documents in knowledge_base/ (public domain).
Each example has two expected outputs: one for prompts without evidence (few-shot) and one that cites
evidence (RAG-enhanced). Review checklist for every output: values copied exactly, no diagnosis, no
treatment advice, no reassurance, abnormalities match flags/range comparisons, citations resolve.
"""

from dataclasses import dataclass
from typing import Any

from app.schemas.summary import SummaryOutput

SAFETY_NOTICE = (
    "This explanation is for education only; please discuss your results with a healthcare professional."
)


@dataclass(frozen=True)
class ExamplePassage:
    citation_id: str
    title: str
    section: str
    url: str
    text: str


@dataclass(frozen=True)
class FewShotExample:
    facts: list[dict[str, Any]]
    passages: list[ExamplePassage]
    output_without_evidence: SummaryOutput
    output_with_evidence: SummaryOutput


def _fact(name: str, value: str, unit: str | None, ref: str | None, flag: str | None, meaning: str | None,
          comparison: str, issues: list[str]) -> dict[str, Any]:
    return {
        "test_name": name,
        "value": value,
        "unit": unit,
        "reference_range": ref,
        "reported_flag": flag,
        "flag_meaning": meaning,
        "range_comparison": comparison,
        "issues": issues,
    }


HEMOGLOBIN_URL = "https://medlineplus.gov/lab-tests/hemoglobin-test/"
GLUCOSE_URL = "https://medlineplus.gov/lab-tests/blood-glucose-test/"
TSH_URL = "https://medlineplus.gov/lab-tests/tsh-thyroid-stimulating-hormone-test/"

EXAMPLE_1 = FewShotExample(
    facts=[
        _fact("Hemoglobin", "10.9", "g/dL", "12.0 - 15.5", "L", "low", "below_range", []),
        _fact("Sodium", "139", "mmol/L", "136 - 145", None, None, "within_range", []),
    ],
    passages=[
        ExamplePassage(
            "E1",
            "Hemoglobin Test",
            "What is a Hemoglobin Test?",
            HEMOGLOBIN_URL,
            "A hemoglobin test measures the levels of hemoglobin in your blood. Hemoglobin is an "
            "iron-rich protein in your red blood cells. It carries oxygen from your lungs to the rest "
            "of your body.",
        ),
        ExamplePassage(
            "E2",
            "Hemoglobin Test",
            "What do the results mean?",
            HEMOGLOBIN_URL,
            "Your results will compare your hemoglobin level to the normal range, which may be called "
            "the reference range. This range may vary, based on the laboratory used and your age, race, "
            "and sex. The test can't tell you what's causing an abnormal level.",
        ),
    ],
    output_without_evidence=SummaryOutput(
        summary=(
            "Your report lists two tests. Hemoglobin is 10.9 g/dL, which is below the range printed on "
            "the report, and the lab marked it with an L flag. Sodium is 139 mmol/L, which is inside the "
            "printed range."
        ),
        test_explanations=[
            {
                "test_name": "Hemoglobin",
                "reported_value": "10.9",
                "unit": "g/dL",
                "reference_range": "12.0 - 15.5",
                "explanation": (
                    "Your result is 10.9 g/dL. The report's range is 12.0 - 15.5 g/dL, so this value is "
                    "below that range. The lab added an L (low) flag."
                ),
                "citation_ids": [],
            },
            {
                "test_name": "Sodium",
                "reported_value": "139",
                "unit": "mmol/L",
                "reference_range": "136 - 145",
                "explanation": "Your result is 139 mmol/L. This is inside the report's range of 136 - 145 mmol/L.",
                "citation_ids": [],
            },
        ],
        reported_abnormalities=[
            {
                "test_name": "Hemoglobin",
                "basis": "report_flag",
                "description": "The lab flagged hemoglobin as low (L). The value 10.9 g/dL is below 12.0 - 15.5.",
            }
        ],
        evidence_citations=[],
        uncertainties=[
            "No reference information was provided, so this summary does not explain what each test measures.",
            "A single result cannot show why a value is outside the range.",
        ],
        questions_for_doctor=[
            "What could explain my hemoglobin result being below the range?",
            "Do I need any follow-up tests?",
            "Should this test be repeated, and when?",
        ],
        safety_notice=SAFETY_NOTICE,
    ),
    output_with_evidence=SummaryOutput(
        summary=(
            "Your report lists two tests. Hemoglobin, a protein in red blood cells that carries oxygen, is "
            "10.9 g/dL. That is below the range printed on the report, and the lab marked it with an L "
            "flag. Sodium is 139 mmol/L, which is inside the printed range."
        ),
        test_explanations=[
            {
                "test_name": "Hemoglobin",
                "reported_value": "10.9",
                "unit": "g/dL",
                "reference_range": "12.0 - 15.5",
                "explanation": (
                    "Hemoglobin is an iron-rich protein in red blood cells that carries oxygen from your "
                    "lungs to the rest of your body. Your result is 10.9 g/dL, which is below the report's "
                    "range of 12.0 - 15.5 g/dL. Ranges can differ between laboratories, and this test alone "
                    "cannot show what is causing a value outside the range."
                ),
                "citation_ids": ["E1", "E2"],
            },
            {
                "test_name": "Sodium",
                "reported_value": "139",
                "unit": "mmol/L",
                "reference_range": "136 - 145",
                "explanation": "Your result is 139 mmol/L. This is inside the report's range of 136 - 145 mmol/L.",
                "citation_ids": [],
            },
        ],
        reported_abnormalities=[
            {
                "test_name": "Hemoglobin",
                "basis": "report_flag",
                "description": "The lab flagged hemoglobin as low (L). The value 10.9 g/dL is below 12.0 - 15.5.",
            }
        ],
        evidence_citations=[
            {"citation_id": "E1", "supports": "Hemoglobin is a protein in red blood cells that carries oxygen."},
            {
                "citation_id": "E2",
                "supports": "Reference ranges vary by laboratory, and the test cannot show the cause of an abnormal level.",
            },
        ],
        uncertainties=["No reference information was available for sodium, so its purpose is not explained."],
        questions_for_doctor=[
            "What could explain my hemoglobin result being below the range?",
            "Do I need any follow-up tests?",
            "Should this test be repeated, and when?",
        ],
        safety_notice=SAFETY_NOTICE,
    ),
)

EXAMPLE_2 = FewShotExample(
    facts=[
        _fact("Glucose", "112", "mg/dL", "70 - 99", None, None, "above_range", []),
        _fact("TSH", "3.0", "mIU/L", None, None, None, "not_compared", ["missing_reference_range"]),
    ],
    passages=[
        ExamplePassage(
            "E1",
            "Blood Glucose Test",
            "What is a blood glucose test?",
            GLUCOSE_URL,
            "A blood glucose test measures the glucose levels in your blood. Glucose is a type of sugar. "
            "It is your body's main source of energy.",
        ),
        ExamplePassage(
            "E2",
            "TSH (Thyroid-stimulating hormone) Test",
            "What is a TSH Test?",
            TSH_URL,
            "TSH stands for thyroid stimulating hormone. Another name for it is thyrotropin. A TSH test is "
            "a blood test that measures this hormone.",
        ),
    ],
    output_without_evidence=SummaryOutput(
        summary=(
            "Your report lists two tests. Glucose is 112 mg/dL, which is above the range printed on the "
            "report; the lab did not add a flag. TSH is 3.0 mIU/L, but no range was printed for it, so it "
            "cannot be compared."
        ),
        test_explanations=[
            {
                "test_name": "Glucose",
                "reported_value": "112",
                "unit": "mg/dL",
                "reference_range": "70 - 99",
                "explanation": (
                    "Your result is 112 mg/dL. The report's range is 70 - 99 mg/dL, so this value is above "
                    "that range. The lab did not flag it."
                ),
                "citation_ids": [],
            },
            {
                "test_name": "TSH",
                "reported_value": "3.0",
                "unit": "mIU/L",
                "reference_range": None,
                "explanation": "Your result is 3.0 mIU/L. No reference range was printed for this test.",
                "citation_ids": [],
            },
        ],
        reported_abnormalities=[
            {
                "test_name": "Glucose",
                "basis": "range_comparison",
                "description": "Glucose 112 mg/dL is above the printed range of 70 - 99. The lab did not flag it.",
            }
        ],
        evidence_citations=[],
        uncertainties=[
            "No reference range was printed for TSH, so it is not compared with a range.",
            "No reference information was provided, so this summary does not explain what each test measures.",
        ],
        questions_for_doctor=[
            "What does my glucose result mean for me?",
            "What range applies to my TSH result?",
        ],
        safety_notice=SAFETY_NOTICE,
    ),
    output_with_evidence=SummaryOutput(
        summary=(
            "Your report lists two tests. Glucose, a sugar that is the body's main source of energy, is "
            "112 mg/dL. That is above the range printed on the report, although the lab did not add a "
            "flag. TSH, a hormone, is 3.0 mIU/L, but no range was printed for it, so it cannot be compared."
        ),
        test_explanations=[
            {
                "test_name": "Glucose",
                "reported_value": "112",
                "unit": "mg/dL",
                "reference_range": "70 - 99",
                "explanation": (
                    "A blood glucose test measures the amount of glucose, a type of sugar, in your blood. "
                    "Glucose is your body's main source of energy. Your result is 112 mg/dL, which is above "
                    "the report's range of 70 - 99 mg/dL. The lab did not flag it."
                ),
                "citation_ids": ["E1"],
            },
            {
                "test_name": "TSH",
                "reported_value": "3.0",
                "unit": "mIU/L",
                "reference_range": None,
                "explanation": (
                    "TSH stands for thyroid stimulating hormone, and this blood test measures that hormone. "
                    "Your result is 3.0 mIU/L. No reference range was printed, so it is not compared with one."
                ),
                "citation_ids": ["E2"],
            },
        ],
        reported_abnormalities=[
            {
                "test_name": "Glucose",
                "basis": "range_comparison",
                "description": "Glucose 112 mg/dL is above the printed range of 70 - 99. The lab did not flag it.",
            }
        ],
        evidence_citations=[
            {"citation_id": "E1", "supports": "A blood glucose test measures glucose, the body's main energy source."},
            {"citation_id": "E2", "supports": "TSH stands for thyroid stimulating hormone; the test measures it."},
        ],
        uncertainties=["No reference range was printed for TSH, so it is not compared with a range."],
        questions_for_doctor=[
            "What does my glucose result mean for me?",
            "What range applies to my TSH result?",
        ],
        safety_notice=SAFETY_NOTICE,
    ),
)

EXAMPLES: tuple[FewShotExample, ...] = (EXAMPLE_1, EXAMPLE_2)
