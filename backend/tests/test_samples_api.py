from fastapi.testclient import TestClient


def test_lists_synthetic_samples(client: TestClient) -> None:
    samples = client.get("/api/samples").json()

    assert samples[0]["id"] == "metabolic_abnormal"
    assert all(s["title"] and s["description"] for s in samples)


def test_serves_sample_pdf_that_extracts(client: TestClient) -> None:
    pdf = client.get("/api/samples/cbc_normal")

    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF-")
    extracted = client.post("/api/reports/extract", files={"file": ("s.pdf", pdf.content, "application/pdf")})
    assert extracted.json()["page_count"] == 1
    assert "SYNTHETIC TEST REPORT" in extracted.json()["pages"][0]["text"]


def test_unknown_sample_is_404(client: TestClient) -> None:
    response = client.get("/api/samples/../../etc/passwd")

    assert response.status_code == 404
    assert client.get("/api/samples/encrypted").status_code == 404
