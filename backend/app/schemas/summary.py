from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.evidence import EvidencePassage
from app.schemas.report import DocumentWarning, Measurement

Strategy = Literal["zero_shot", "few_shot", "rag"]
STRATEGIES: tuple[Strategy, ...] = ("zero_shot", "few_shot", "rag")


# ---- Structured output requested from the LLM (also sent to Gemini as the JSON schema) ----


class TestExplanation(BaseModel):
    __test__ = False  # not a pytest test class

    test_name: str = Field(description="Exactly as given in report_facts.")
    reported_value: str = Field(description="Copied exactly from report_facts.value.")
    unit: str | None = Field(description="Copied exactly from report_facts.unit, or null.")
    reference_range: str | None = Field(description="Copied exactly from report_facts.reference_range, or null.")
    explanation: str = Field(description="Plain-language explanation for a non-medical reader.")
    citation_ids: list[str] = Field(description="IDs of reference passages supporting background statements.")


class ReportedAbnormality(BaseModel):
    test_name: str
    basis: Literal["report_flag", "range_comparison"] = Field(
        description="report_flag if the laboratory flagged it; range_comparison if only the printed range shows it."
    )
    description: str


class EvidenceCitation(BaseModel):
    citation_id: str
    supports: str = Field(description="The statement this passage supports.")


class SummaryOutput(BaseModel):
    summary: str
    test_explanations: list[TestExplanation]
    reported_abnormalities: list[ReportedAbnormality]
    evidence_citations: list[EvidenceCitation]
    uncertainties: list[str]
    questions_for_doctor: list[str]
    safety_notice: str


# ---- API response ----


class ValidationIssue(BaseModel):
    code: str
    severity: Literal["error", "warning"]
    message: str
    location: str | None = None


class ValidationReport(BaseModel):
    status: Literal["passed", "passed_with_warnings", "failed"]
    issues: list[ValidationIssue]
    checks_run: list[str]
    note: str = (
        "Automated checks compare the output with the report and the retrieved sources. "
        "They reduce risk but do not guarantee medical accuracy."
    )


class TokenUsage(BaseModel):
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class SummaryResponse(BaseModel):
    strategy: Strategy
    model: str
    prompt_version: str
    prompt_sha256: str
    output: SummaryOutput
    validation: ValidationReport
    measurements: list[Measurement]
    document_warnings: list[DocumentWarning]
    evidence: list[EvidencePassage]
    unmatched_tests: list[str]
    usage: TokenUsage
    latency_ms: int
    disclaimer: str
