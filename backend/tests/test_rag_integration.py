"""Retrieval relevance on the real corpus, real model and real index.

Skipped unless the index has been built (`python -m scripts.ingest_knowledge_base`). Run only these with
`pytest -m integration`.
"""

import pytest

from app.config import get_settings
from app.rag.embeddings import SentenceTransformerEmbedder
from app.rag.retrieval import Retriever
from app.rag.store import VectorStore

settings = get_settings()
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not (settings.index_dir / "chroma.sqlite3").exists(),
        reason="knowledge base index not built",
    ),
]

# Test name as printed on the synthetic reports -> source that should answer it.
EXPECTED_SOURCES = {
    "Hemoglobin": "medlineplus-hemoglobin-test",
    "Hematocrit": "medlineplus-hematocrit-test",
    "WBC": "medlineplus-white-blood-count-wbc",
    "Platelets": "medlineplus-platelet-tests",
    "Glucose, Fasting": "medlineplus-blood-glucose-test",
    "LDL Cholesterol": "medlineplus-cholesterol-levels",
    "HDL Cholesterol": "medlineplus-cholesterol-levels",
    "Potassium": "medlineplus-potassium-blood-test",
    "Sodium": "medlineplus-sodium-blood-test",
    "HbA1c": "medlineplus-hemoglobin-a1c-hba1c-test",
    "TSH": "medlineplus-tsh-thyroid-stimulating-hormone-test",
    "Vitamin B12": "medlineplus-vitamin-b-test",
    "CRP": "medlineplus-c-reactive-protein-crp-test",
    "Creatinine": "medlineplus-creatinine-test",
}
# Tests with no source in the corpus, plus off-topic queries: must get no evidence.
NOT_IN_CORPUS = ["Ferritin", "PSA", "Lipase", "Troponin I", "Urine culture", "Weather forecast"]


@pytest.fixture(scope="module")
def retriever() -> Retriever:
    return Retriever(
        VectorStore(settings.index_dir),
        SentenceTransformerEmbedder(settings.embedding_model),
        top_k=settings.rag_top_k,
        min_similarity=settings.rag_min_similarity,
    )


def test_top_passage_comes_from_expected_source(retriever: Retriever) -> None:
    response = retriever.retrieve_for_tests(list(EXPECTED_SOURCES))
    passages = {p.citation_id: p for p in response.passages}

    assert response.unmatched_tests == []
    for test in response.tests:
        top = passages[test.citation_ids[0]]
        assert top.source_id == EXPECTED_SOURCES[test.test_name], test.test_name


def test_tests_outside_the_corpus_get_no_evidence(retriever: Retriever) -> None:
    response = retriever.retrieve_for_tests(NOT_IN_CORPUS)

    assert response.unmatched_tests == NOT_IN_CORPUS
    assert response.passages == []
