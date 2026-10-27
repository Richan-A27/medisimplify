from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.evidence import get_knowledge_base
from app.main import create_app
from app.rag.ingest import ingest
from app.rag.retrieval import KnowledgeBaseUnavailableError, Retriever, build_query
from app.rag.store import VectorStore
from tests.conftest import make_settings
from tests.rag_fakes import SAMPLE_DOCUMENTS, HashingEmbedder, write_corpus


class StubKnowledgeBase:
    def __init__(self, retriever: Retriever) -> None:
        self._retriever = retriever

    def retriever(self) -> Retriever:
        return self._retriever


@pytest.fixture
def store(tmp_path: Path) -> VectorStore:
    write_corpus(tmp_path / "sources", SAMPLE_DOCUMENTS)
    store = VectorStore(tmp_path / "index")
    ingest(tmp_path / "sources", store, HashingEmbedder(), max_words=60, overlap_words=10)
    return store


@pytest.fixture
def retriever(store: VectorStore) -> Retriever:
    return Retriever(store, HashingEmbedder(), top_k=2, min_similarity=0.2)


def test_ingestion_records_build_metadata(store: VectorStore) -> None:
    info = store.info()

    assert info is not None
    assert info["chunk_count"] == 4
    assert info["source_count"] == 3
    assert info["embedding_model"] == "test/hashing-embedder"
    assert len(info["corpus_sha256"]) == 64


def test_rebuild_replaces_previous_index(tmp_path: Path, store: VectorStore) -> None:
    ingest(tmp_path / "sources", store, HashingEmbedder(), max_words=60, overlap_words=10)

    assert store.info()["chunk_count"] == 4  # type: ignore[index]


def test_retrieves_matching_source_with_citations(retriever: Retriever) -> None:
    response = retriever.retrieve_for_tests(["Hemoglobin", "Glucose"])

    by_id = {p.citation_id: p for p in response.passages}
    hemoglobin, glucose = response.tests
    assert hemoglobin.citation_ids and by_id[hemoglobin.citation_ids[0]].source_id == "doc-hemoglobin"
    assert glucose.citation_ids and by_id[glucose.citation_ids[0]].source_id == "doc-glucose"
    passage = by_id[hemoglobin.citation_ids[0]]
    assert passage.url == "https://example.test/doc-hemoglobin"
    assert passage.title == "Hemoglobin Test"
    assert passage.attribution == "Source: Test Publisher"


def test_every_citation_id_resolves_to_a_unique_passage(retriever: Retriever) -> None:
    response = retriever.retrieve_for_tests(["Hemoglobin", "Hgb", "Potassium"])

    passage_ids = [p.citation_id for p in response.passages]
    assert len(passage_ids) == len(set(passage_ids))
    assert passage_ids == [f"E{i}" for i in range(1, len(passage_ids) + 1)]
    for test in response.tests:
        assert set(test.citation_ids) <= set(passage_ids)
    assert len({p.chunk_id for p in response.passages}) == len(response.passages)


def test_irrelevant_test_gets_no_evidence(retriever: Retriever) -> None:
    response = retriever.retrieve_for_tests(["Zinc protoporphyrin"])

    assert response.unmatched_tests == ["Zinc protoporphyrin"]
    assert response.tests[0].citation_ids == []
    assert response.passages == []


def test_empty_index_raises_unavailable(tmp_path: Path) -> None:
    retriever = Retriever(VectorStore(tmp_path / "empty"), HashingEmbedder(), top_k=2, min_similarity=0.2)

    with pytest.raises(KnowledgeBaseUnavailableError):
        retriever.retrieve_for_tests(["Hemoglobin"])


def test_model_mismatch_raises_unavailable(store: VectorStore) -> None:
    class OtherEmbedder(HashingEmbedder):
        model_name = "test/other-model"

    with pytest.raises(KnowledgeBaseUnavailableError, match="different embedding model"):
        Retriever(store, OtherEmbedder(), top_k=2, min_similarity=0.2).retrieve_for_tests(["Hemoglobin"])


def test_query_uses_test_name_only_and_expands_abbreviations() -> None:
    assert build_query("WBC").startswith("white blood cell count test")
    assert build_query("HbA1c").startswith("hemoglobin A1C test")
    assert build_query("Glucose, Fasting").startswith("Glucose Fasting test")


def test_evidence_endpoint(retriever: Retriever) -> None:
    app = create_app(make_settings())
    app.dependency_overrides[get_knowledge_base] = lambda: StubKnowledgeBase(retriever)
    client = TestClient(app)

    response = client.post("/api/evidence/retrieve", json={"test_names": ["Hemoglobin", " hemoglobin ", "Zinc"]})

    assert response.status_code == 200
    body = response.json()
    assert [t["test_name"] for t in body["tests"]] == ["Hemoglobin", "Zinc"]  # deduplicated
    assert body["unmatched_tests"] == ["Zinc"]
    assert body["embedding_model"] == "test/hashing-embedder"


@pytest.mark.parametrize("payload", [{"test_names": []}, {"test_names": ["x" * 101]}, {}])
def test_evidence_endpoint_validates_input(client: TestClient, payload: dict) -> None:
    response = client.post("/api/evidence/retrieve", json=payload)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_evidence_endpoint_reports_missing_index(tmp_path: Path) -> None:
    app = create_app(make_settings())
    app.dependency_overrides[get_knowledge_base] = lambda: StubKnowledgeBase(
        Retriever(VectorStore(tmp_path / "empty"), HashingEmbedder(), top_k=2, min_similarity=0.2)
    )

    response = TestClient(app).post("/api/evidence/retrieve", json={"test_names": ["Hemoglobin"]})

    assert response.status_code == 503
    assert response.json()["code"] == "knowledge_base_unavailable"
    assert "ingest_knowledge_base" in response.json()["message"]


def test_evidence_endpoint_without_index_directory(client: TestClient) -> None:
    response = client.post("/api/evidence/retrieve", json={"test_names": ["Hemoglobin"]})

    assert response.status_code == 503
    assert response.json()["code"] == "knowledge_base_unavailable"


def test_health_reports_missing_knowledge_base(client: TestClient) -> None:
    body = client.get("/api/health").json()

    assert body["knowledge_base"]["index_ready"] is False
    assert body["knowledge_base"]["chunk_count"] == 0
