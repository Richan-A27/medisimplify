import json
import logging
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.evidence import get_knowledge_base
from app.api.reports import get_llm
from app.main import create_app
from app.rag.ingest import ingest
from app.rag.retrieval import Retriever
from app.rag.store import VectorStore
from app.services.llm import LLMQuotaError, LLMTimeoutError
from scripts.synthetic_reports import REPORTS, text_pdf
from tests.conftest import make_settings
from tests.llm_fakes import FakeLLM
from tests.rag_fakes import SAMPLE_DOCUMENTS, HashingEmbedder, write_corpus

URL = "/api/reports/summarize"


class StubKnowledgeBase:
    def __init__(self, retriever: Retriever | None) -> None:
        self._retriever = retriever

    def retriever(self) -> Retriever:
        if self._retriever is None:
            from app.rag.retrieval import KnowledgeBaseUnavailableError

            raise KnowledgeBaseUnavailableError()
        return self._retriever


@pytest.fixture
def retriever(tmp_path: Path) -> Retriever:
    write_corpus(tmp_path / "sources", SAMPLE_DOCUMENTS)
    store = VectorStore(tmp_path / "index")
    ingest(tmp_path / "sources", store, HashingEmbedder(), max_words=60, overlap_words=10)
    return Retriever(store, HashingEmbedder(), top_k=2, min_similarity=0.2)


def make_app(llm: FakeLLM | None, retriever: Retriever | None = None) -> FastAPI:
    app = create_app(make_settings())
    app.dependency_overrides[get_llm] = lambda: llm
    app.dependency_overrides[get_knowledge_base] = lambda: StubKnowledgeBase(retriever)
    return app


def post(app: FastAPI, report: str = "metabolic_abnormal", strategy: str = "rag"):
    pdf = text_pdf([REPORTS[report]])
    return TestClient(app).post(URL, files={"file": ("r.pdf", pdf, "application/pdf")}, data={"strategy": strategy})


@pytest.mark.parametrize("strategy", ["zero_shot", "few_shot", "rag"])
def test_summary_for_each_strategy(strategy: str, retriever: Retriever) -> None:
    llm = FakeLLM()

    response = post(make_app(llm, retriever), strategy=strategy)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["strategy"] == strategy
    assert body["model"] == "fake-model"
    assert body["validation"]["status"] == "passed", body["validation"]["issues"]
    assert len(body["output"]["test_explanations"]) == 6
    assert body["usage"] == {"prompt_tokens": 100, "output_tokens": 50, "total_tokens": 150}
    assert "not a diagnosis" in body["disclaimer"]
    assert len(llm.prompts) == 1
    if strategy == "rag":
        assert body["evidence"], "rag should retrieve passages"
        cited = {c for t in body["output"]["test_explanations"] for c in t["citation_ids"]}
        assert cited <= {p["citation_id"] for p in body["evidence"]}
    else:
        assert body["evidence"] == []


def test_same_report_and_settings_give_same_facts_across_strategies(retriever: Retriever) -> None:
    llm = FakeLLM()
    app = make_app(llm, retriever)

    hashes = {post(app, strategy=s).json()["prompt_sha256"] for s in ("zero_shot", "few_shot", "rag")}

    assert len(hashes) == 3
    final_facts = {p.messages[-1].text.split("</report_facts_")[0].split(">", 1)[1] for p in llm.prompts}
    assert len(final_facts) == 1


def test_missing_api_key_returns_clear_error() -> None:
    response = post(make_app(None), strategy="zero_shot")

    assert response.status_code == 503
    assert response.json()["code"] == "llm_not_configured"
    assert "GEMINI_API_KEY" in response.json()["message"]


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [(LLMQuotaError(), 429, "llm_quota_exceeded"), (LLMTimeoutError(), 504, "llm_timeout")],
)
def test_llm_failures_are_reported(error: Exception, status: int, code: str) -> None:
    response = post(make_app(FakeLLM(error=error)), strategy="zero_shot")  # type: ignore[arg-type]

    assert response.status_code == status
    assert response.json()["code"] == code


@pytest.mark.parametrize("text", ["not json", '{"summary": "missing fields"}', "[]"])
def test_malformed_output_is_rejected(text: str) -> None:
    response = post(make_app(FakeLLM(respond=lambda _: text)), strategy="zero_shot")

    assert response.status_code == 502
    assert response.json()["code"] == "llm_invalid_output"


def test_unsafe_output_is_returned_with_failed_validation() -> None:
    def unsafe(prompt):  # noqa: ANN001, ANN202
        data = json.loads(FakeLLM._safe_response(prompt))
        data["summary"] = "Your results are normal and you are perfectly healthy."
        data["test_explanations"][0]["reported_value"] = "99"
        return json.dumps(data)

    response = post(make_app(FakeLLM(respond=unsafe)), strategy="zero_shot")

    assert response.status_code == 200
    validation = response.json()["validation"]
    assert validation["status"] == "failed"
    assert {"false_reassurance", "value_mismatch"} <= {i["code"] for i in validation["issues"]}


def test_report_without_results_does_not_call_llm() -> None:
    llm = FakeLLM()

    response = post(make_app(llm), report="no_results", strategy="zero_shot")

    assert response.status_code == 422
    assert response.json()["code"] == "no_measurements"
    assert llm.prompts == []


def test_rag_without_index_returns_503() -> None:
    response = post(make_app(FakeLLM(), retriever=None), strategy="rag")

    assert response.status_code == 503
    assert response.json()["code"] == "knowledge_base_unavailable"


def test_invalid_strategy_is_rejected() -> None:
    response = post(make_app(FakeLLM()), strategy="chain_of_thought")

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_prompt_injection_report_is_processed_as_data(retriever: Retriever) -> None:
    llm = FakeLLM()

    response = post(make_app(llm, retriever), report="prompt_injection", strategy="rag")

    assert response.status_code == 200
    body = response.json()
    assert "possible_embedded_instructions" in {w["code"] for w in body["document_warnings"]}
    sent = "\n".join(m.text for m in llm.prompts[0].messages)
    assert "Ignore all previous instructions" not in sent
    assert "reveal your API key" not in sent


def test_summary_logs_contain_no_report_content(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        post(make_app(FakeLLM()), strategy="zero_shot")

    assert "Summary: strategy=zero_shot" in caplog.text
    for secret in ("Glucose", "128", "Test Patient A"):
        assert secret not in caplog.text


def test_health_does_not_expose_key() -> None:
    client = TestClient(create_app(make_settings(gemini_api_key="secret-xyz")))

    assert "secret-xyz" not in client.get("/api/health").text
