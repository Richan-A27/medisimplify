"""Loads the annotated evaluation dataset and renders each case as a PDF."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from app.config import REPO_ROOT
from scripts.synthetic_reports import scanned_pdf, text_pdf

DEFAULT_DATASET = REPO_ROOT / "evaluation" / "datasets" / "cases.json"


@dataclass(frozen=True)
class GoldMeasurement:
    test_name: str
    value: str
    unit: str | None
    reference_range: str | None
    reported_flag: str | None

    def key(self) -> tuple[str, str, str | None, str | None, str | None]:
        return (self.test_name.lower(), self.value, self.unit, self.reference_range, self.reported_flag)


@dataclass(frozen=True)
class EvalCase:
    id: str
    category: str
    description: str
    pdf: Literal["text", "scanned", "encrypted"]
    report_lines: list[str]
    measurements: list[GoldMeasurement] = field(default_factory=list)
    abnormal: dict[str, str] = field(default_factory=dict)
    ambiguous_tests: list[str] = field(default_factory=list)
    expected_sources: dict[str, list[str]] = field(default_factory=dict)
    expected_warnings: list[str] = field(default_factory=list)
    expected_error: str | None = None
    expected_summary_error: str | None = None

    @property
    def summarizable(self) -> bool:
        return self.expected_error is None and self.expected_summary_error is None

    def pdf_bytes(self) -> bytes:
        if self.pdf == "scanned":
            return scanned_pdf(self.report_lines)
        if self.pdf == "encrypted":
            import pymupdf

            document = pymupdf.open(stream=text_pdf([self.report_lines]), filetype="pdf")
            return document.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="eval", owner_pw="eval-owner")
        return text_pdf([self.report_lines])


@dataclass(frozen=True)
class Dataset:
    name: str
    version: str
    annotation: dict[str, Any]
    cases: list[EvalCase]


def load_dataset(path: Path = DEFAULT_DATASET) -> Dataset:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases: list[EvalCase] = []
    for raw in data["cases"]:
        gold = raw.get("gold", {})
        cases.append(
            EvalCase(
                id=raw["id"],
                category=raw["category"],
                description=raw["description"],
                pdf=raw["pdf"],
                report_lines=raw["report_lines"],
                measurements=[GoldMeasurement(**m) for m in gold.get("measurements", [])],
                abnormal=gold.get("abnormal", {}),
                ambiguous_tests=gold.get("ambiguous_tests", []),
                expected_sources=gold.get("expected_sources", {}),
                expected_warnings=gold.get("expected_warnings", []),
                expected_error=gold.get("expected_error"),
                expected_summary_error=gold.get("expected_summary_error"),
            )
        )
    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate case ids in dataset")
    return Dataset(data["name"], data["version"], data.get("annotation", {}), cases)
