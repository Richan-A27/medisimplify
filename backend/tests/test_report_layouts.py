"""Layouts seen in real lab reports: column tables, ranges printed below the row, stratified ranges."""

import pytest

from app.services.pdf_extraction import PageText, PyMuPDFTextExtractor
from app.services.report_parser import parse_line, parse_measurements
from scripts.synthetic_reports import REPORTS, text_pdf


@pytest.fixture(scope="module")
def results() -> dict[str, object]:
    pages = PyMuPDFTextExtractor(30).extract(text_pdf([REPORTS["columnar_lab"]])).pages
    return {m.test_name: m for m in parse_measurements(pages)}


def test_method_column_is_not_part_of_the_test_name(results: dict) -> None:
    assert {"VITAMIN K", "VITAMIN A", "VITAMIN B-12", "SERUM ZINC", "VITAMIN D TOTAL"} == set(results)


def test_range_printed_below_the_row_is_attached_and_compared(results: dict) -> None:
    vitamin_k = results["VITAMIN K"]

    assert (vitamin_k.value, vitamin_k.unit, vitamin_k.reference_range) == ("0.41", "ng/mL", "0.13 - 1.19")
    assert vitamin_k.range_comparison == "within_range"
    assert vitamin_k.source_status == "complete"
    assert "0.13 - 1.19" in vitamin_k.source_line


def test_age_table_is_kept_verbatim_and_not_compared(results: dict) -> None:
    vitamin_a = results["VITAMIN A"]

    assert vitamin_a.reference_range == "1 - 6 Years 200 - 400; Above 18 Years 300 - 800"
    assert vitamin_a.range_comparison == "not_compared"
    assert "stratified_reference_range" in vitamin_a.issues
    assert vitamin_a.source_status == "incomplete"


def test_column_row_with_inline_range(results: dict) -> None:
    b12 = results["VITAMIN B-12"]

    assert (b12.value, b12.unit, b12.reference_range, b12.range_comparison) == ("188", "pg/mL", "197-771", "below_range")


def test_summary_and_detail_copies_merge_preferring_simple_range(results: dict) -> None:
    vitamin_d = results["VITAMIN D TOTAL"]

    assert vitamin_d.reference_range == "30-100"
    assert vitamin_d.range_comparison == "below_range"
    assert "duplicate_test_conflicting_values" not in vitamin_d.issues


@pytest.mark.parametrize(
    "line",
    [
        "Above 18 Years    300 - 800",
        "Deficiency   : <20 ng/mL",
        "Processed At : Plot No.12, Sample Road, Testville - 122 015",
        "Industrial Area, Testville, Somestate - 122 015",
        "Elements 22 (Toxic And Nutrients) + 1 Other",
        "7 Ready              0 Ready with Cancellation       0 Processing",
    ],
)
def test_range_rows_addresses_and_headers_are_not_tests(line: str) -> None:
    assert parse_line(line, 1) is None


def test_range_block_is_not_attached_across_another_result() -> None:
    page = PageText(
        1,
        "ALPHA TEST      METHOD-X      1.0      mg/L\n"
        "BETA TEST       METHOD-X      2.0      mg/L\n"
        "Bio. Ref. Interval. :-\n"
        "1.5 - 2.5",
    )

    results = {m.test_name: m for m in parse_measurements([page])}

    assert results["ALPHA TEST"].reference_range is None
    assert results["BETA TEST"].reference_range == "1.5 - 2.5"
