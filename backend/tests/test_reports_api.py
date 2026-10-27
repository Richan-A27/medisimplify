import logging

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from scripts.synthetic_reports import (
    REPORTS,
    encrypted_pdf,
    partially_scanned_pdf,
    scanned_pdf,
    text_pdf,
)
from tests.conftest import make_settings

URL = "/api/reports/extract"


def upload(client: TestClient, data: bytes, filename: str = "report.pdf", content_type: str = "application/pdf"):
    return client.post(URL, files={"file": (filename, data, content_type)})


def by_name(body: dict) -> dict[str, dict]:
    return {m["test_name"]: m for m in body["measurements"]}


def test_extracts_normal_report(client: TestClient) -> None:
    response = upload(client, text_pdf([REPORTS["cbc_normal"]]))

    assert response.status_code == 200
    body = response.json()
    assert body["page_count"] == 1
    assert body["extraction_method"] == "pymupdf_text_layer"
    assert "Hemoglobin 13.8 g/dL 12.0 - 15.5" in body["pages"][0]["text"]
    results = by_name(body)
    assert set(results) == {"Hemoglobin", "Hematocrit", "WBC", "Platelets"}
    assert results["WBC"]["unit"] == "x10^3/uL"
    assert all(m["range_comparison"] == "within_range" for m in results.values())
    assert body["warnings"] == []


def test_extracts_abnormal_values_and_flags(client: TestClient) -> None:
    body = upload(client, text_pdf([REPORTS["metabolic_abnormal"]])).json()
    results = by_name(body)

    assert results["Glucose, Fasting"]["reported_flag"] == "H"
    assert results["Potassium"]["flag_meaning"] == "low"
    assert results["LDL Cholesterol"]["range_comparison"] == "above_range"
    assert results["LDL Cholesterol"]["reported_flag"] is None
    assert results["Sodium"]["range_comparison"] == "within_range"


def test_every_reported_value_appears_verbatim_in_source(client: TestClient) -> None:
    for name in ("cbc_normal", "metabolic_abnormal", "missing_ranges", "conflicting_values"):
        body = upload(client, text_pdf([REPORTS[name]])).json()
        text = body["pages"][0]["text"]
        for m in body["measurements"]:
            assert m["source_line"] in text
            for field in ("value", "unit", "reference_range"):
                if m[field] is not None:
                    assert m[field] in m["source_line"], (name, field, m)


def test_missing_ranges_and_conflicts_produce_warnings(client: TestClient) -> None:
    missing = upload(client, text_pdf([REPORTS["missing_ranges"]])).json()
    assert by_name(missing)["TSH"]["source_status"] == "incomplete"

    conflicting = upload(client, text_pdf([REPORTS["conflicting_values"]])).json()
    assert "ambiguous_measurements" in {w["code"] for w in conflicting["warnings"]}


def test_scanned_pdf_is_rejected_with_clear_message(client: TestClient) -> None:
    response = upload(client, scanned_pdf(REPORTS["cbc_normal"]))

    assert response.status_code == 422
    assert response.json()["code"] == "no_extractable_text"
    assert "scanned" in response.json()["message"]


def test_partially_scanned_pdf_warns_about_skipped_page(client: TestClient) -> None:
    body = upload(client, partially_scanned_pdf()).json()

    assert body["page_count"] == 2
    assert {"code": "page_without_text", "page_number": 2} == {
        k: v for k, v in body["warnings"][0].items() if k in ("code", "page_number")
    }
    assert body["pages"][1]["has_text"] is False


def test_prompt_injection_is_flagged_and_kept_as_data(client: TestClient) -> None:
    body = upload(client, text_pdf([REPORTS["prompt_injection"]])).json()

    assert "possible_embedded_instructions" in {w["code"] for w in body["warnings"]}
    assert list(by_name(body)) == ["Hemoglobin"]
    assert "Ignore all previous instructions" in body["pages"][0]["text"]


def test_report_without_results_warns(client: TestClient) -> None:
    body = upload(client, text_pdf([REPORTS["no_results"]])).json()

    assert body["measurements"] == []
    assert "no_measurements_found" in {w["code"] for w in body["warnings"]}


@pytest.mark.parametrize(
    ("data", "content_type", "status", "code"),
    [
        (b"", "application/pdf", 400, "empty_file"),
        (b"just some text, not a pdf", "application/pdf", 415, "invalid_file_type"),
        (b"%PDF-1.7\n this is not really a pdf", "application/pdf", 422, "unreadable_pdf"),
        (b"%PDF-1.7", "image/png", 415, "invalid_file_type"),
    ],
)
def test_invalid_uploads(client: TestClient, data: bytes, content_type: str, status: int, code: str) -> None:
    response = upload(client, data, content_type=content_type)

    assert response.status_code == status
    assert response.json()["code"] == code


def test_encrypted_pdf_is_rejected(client: TestClient) -> None:
    response = upload(client, encrypted_pdf())

    assert response.status_code == 422
    assert response.json()["code"] == "encrypted_pdf"


def test_oversized_upload_is_rejected() -> None:
    client = TestClient(create_app(make_settings(max_upload_mb=1)))

    response = upload(client, b"%PDF-1.7\n" + b"0" * (1024 * 1024 + 1))

    assert response.status_code == 413
    assert response.json()["code"] == "file_too_large"


def test_page_limit_is_enforced() -> None:
    client = TestClient(create_app(make_settings(max_pdf_pages=1)))

    response = upload(client, text_pdf([REPORTS["cbc_normal"], REPORTS["cbc_normal"]]))

    assert response.status_code == 422
    assert response.json()["code"] == "too_many_pages"


def test_missing_file_field_returns_validation_error(client: TestClient) -> None:
    response = client.post(URL)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_report_contents_are_not_logged(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        upload(client, text_pdf([REPORTS["metabolic_abnormal"]]))

    assert "Extracted report" in caplog.text
    for secret in ("Test Patient A", "Glucose", "128", "01/01/1980"):
        assert secret not in caplog.text
