from typing import Literal

from pydantic import BaseModel, Field

FlagMeaning = Literal["high", "low", "critical", "abnormal"]
RangeComparison = Literal["above_range", "below_range", "within_range", "not_compared"]
SourceStatus = Literal["complete", "incomplete", "ambiguous"]
MeasurementIssue = Literal[
    "missing_unit",
    "missing_reference_range",
    "value_is_bound",
    "multiple_ranges_found",
    "flag_conflicts_with_range",
    "duplicate_test_conflicting_values",
    "unrecognized_text",
]


class Measurement(BaseModel):
    """A test result candidate copied from the report. Text fields are exactly as printed."""

    test_name: str
    value: str
    value_numeric: float | None = Field(
        description="Parsed number; null when the value is a bound such as '<0.5'."
    )
    unit: str | None
    reference_range: str | None
    reported_flag: str | None = Field(description="Flag printed in the report, e.g. 'H'.")
    flag_meaning: FlagMeaning | None
    range_comparison: RangeComparison = Field(
        description="Independent comparison of the value with the printed range. "
        "This is arithmetic only, not a clinical interpretation."
    )
    source_status: SourceStatus
    issues: list[MeasurementIssue]
    page_number: int
    source_line: str


class PageTextOut(BaseModel):
    page_number: int
    text: str
    has_text: bool


class DocumentWarning(BaseModel):
    code: str
    message: str
    page_number: int | None = None


class ExtractionResponse(BaseModel):
    page_count: int
    extraction_method: str
    character_count: int
    pages: list[PageTextOut]
    measurements: list[Measurement]
    warnings: list[DocumentWarning]
