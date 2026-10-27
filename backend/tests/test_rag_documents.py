import json
from pathlib import Path

import pytest

from app.config import REPO_ROOT
from app.rag.chunking import chunk_document, split_sentences
from app.rag.documents import DocumentError, load_documents, parse_document, render_document
from tests.rag_fakes import SAMPLE_DOCUMENTS, make_document, write_corpus

REAL_SOURCES = REPO_ROOT / "knowledge_base" / "sources"


def test_document_round_trips_through_markdown() -> None:
    original = SAMPLE_DOCUMENTS[0]

    parsed = parse_document(render_document(original))

    assert parsed == original


def test_missing_metadata_is_rejected() -> None:
    with pytest.raises(DocumentError, match="url"):
        parse_document("---\nid: x\ntitle: T\npublisher: P\nlicense: L\nattribution: A\n---\n## S\ntext\n")


def test_unapproved_document_is_rejected(tmp_path: Path) -> None:
    write_corpus(tmp_path, SAMPLE_DOCUMENTS)
    extra = make_document("doc-unreviewed", "Unreviewed", {"Section": "Some text."})
    (tmp_path / "documents" / "doc-unreviewed.md").write_text(render_document(extra))

    with pytest.raises(DocumentError, match="not approved"):
        load_documents(tmp_path)


def test_url_must_match_manifest(tmp_path: Path) -> None:
    write_corpus(tmp_path, SAMPLE_DOCUMENTS)
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    manifest["sources"][0]["url"] = "https://example.test/other"
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))

    with pytest.raises(DocumentError, match="URL does not match"):
        load_documents(tmp_path)


def test_missing_approved_document_is_reported(tmp_path: Path) -> None:
    write_corpus(tmp_path, SAMPLE_DOCUMENTS)
    (tmp_path / "documents" / "doc-glucose.md").unlink()

    with pytest.raises(DocumentError, match="doc-glucose"):
        load_documents(tmp_path)


def test_bundled_corpus_is_complete_and_attributed() -> None:
    documents = load_documents(REAL_SOURCES)

    assert len(documents) == 20
    for document in documents:
        assert document.url.startswith("https://medlineplus.gov/lab-tests/")
        assert document.license == "Public domain (U.S. federal government work)"
        assert document.attribution == "Source: MedlinePlus, National Library of Medicine"
        assert document.retrieved
        assert len(document.sections) >= 5
        headings = {s.heading.lower() for s in document.sections}
        assert "references" not in headings


def test_chunks_respect_size_overlap_and_section_boundaries() -> None:
    document = make_document(
        "doc-long",
        "Long",
        {
            "First": " ".join(f"Sentence number {i} talks about blood tests." for i in range(40)),
            "Second": "A short section.",
        },
    )

    chunks = chunk_document(document, max_words=50, overlap_words=15)

    first = [c for c in chunks if c.section == "First"]
    assert len(first) > 1
    assert all(len(c.text.split()) <= 50 for c in first)
    for previous, current in zip(first, first[1:]):
        previous_sentences = previous.text.split("\n")
        assert current.text.split("\n")[0] in previous_sentences  # starts inside the previous chunk
        assert previous_sentences[-1] in current.text  # and repeats its last sentence
    assert [c.text for c in chunks if c.section == "Second"] == ["A short section."]
    assert len({c.id for c in chunks}) == len(chunks)


def test_chunk_text_is_copied_from_source_without_changes() -> None:
    for document in load_documents(REAL_SOURCES)[:5]:
        sentences = {s for section in document.sections for s in split_sentences(section.text)}
        for chunk in chunk_document(document, max_words=160, overlap_words=40):
            assert all(sentence in sentences for sentence in chunk.text.split("\n"))


def test_overlap_must_be_smaller_than_chunk() -> None:
    with pytest.raises(ValueError):
        chunk_document(SAMPLE_DOCUMENTS[0], max_words=20, overlap_words=20)
