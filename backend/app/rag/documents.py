"""Reference documents: an approved-source manifest plus one Markdown file per source.

Document format (`knowledge_base/sources/documents/<id>.md`):

    ---
    id: medlineplus-hemoglobin-test
    title: Hemoglobin Test
    ...other metadata...
    ---
    ## Section heading
    Section text...

Only documents whose `id` is listed in `manifest.json` are loaded, so adding a file is not enough to
put it in the index: the source must be reviewed and approved in the manifest first.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

REQUIRED_METADATA = ("id", "title", "publisher", "url", "license", "attribution")


class DocumentError(ValueError):
    pass


@dataclass(frozen=True)
class Section:
    heading: str
    text: str


@dataclass(frozen=True)
class SourceDocument:
    id: str
    title: str
    publisher: str
    url: str
    license: str
    attribution: str
    source_last_updated: str | None = None
    retrieved: str | None = None
    sections: list[Section] = field(default_factory=list)


def load_manifest(sources_dir: Path) -> dict[str, dict[str, str]]:
    path = sources_dir / "manifest.json"
    if not path.exists():
        raise DocumentError(f"Missing source manifest: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return {entry["id"]: entry for entry in data["sources"]}


def parse_document(text: str) -> SourceDocument:
    if not text.startswith("---\n"):
        raise DocumentError("Document must start with a '---' metadata block.")
    header, _, body = text[4:].partition("\n---\n")
    metadata: dict[str, str] = {}
    for line in header.splitlines():
        key, sep, value = line.partition(":")
        if sep:
            metadata[key.strip()] = value.strip()
    missing = [key for key in REQUIRED_METADATA if not metadata.get(key)]
    if missing:
        raise DocumentError(f"Document is missing metadata: {', '.join(missing)}")

    sections: list[Section] = []
    heading: str | None = None
    lines: list[str] = []
    for line in body.splitlines():
        if line.startswith("## "):
            if heading is not None:
                sections.append(Section(heading, "\n".join(lines).strip()))
            heading, lines = line[3:].strip(), []
        elif heading is not None:
            lines.append(line)
    if heading is not None:
        sections.append(Section(heading, "\n".join(lines).strip()))

    return SourceDocument(
        id=metadata["id"],
        title=metadata["title"],
        publisher=metadata["publisher"],
        url=metadata["url"],
        license=metadata["license"],
        attribution=metadata["attribution"],
        source_last_updated=metadata.get("source_last_updated") or None,
        retrieved=metadata.get("retrieved") or None,
        sections=[s for s in sections if s.text],
    )


def load_documents(sources_dir: Path) -> list[SourceDocument]:
    """Load approved documents. Raises if an approved source is missing or a file is unapproved."""
    approved = load_manifest(sources_dir)
    documents: list[SourceDocument] = []
    seen: set[str] = set()
    for path in sorted((sources_dir / "documents").glob("*.md")):
        document = parse_document(path.read_text(encoding="utf-8"))
        if document.id not in approved:
            raise DocumentError(f"{path.name}: source '{document.id}' is not approved in manifest.json")
        if document.url != approved[document.id]["url"]:
            raise DocumentError(f"{path.name}: URL does not match the approved manifest entry")
        if not document.sections:
            raise DocumentError(f"{path.name}: document has no content sections")
        documents.append(document)
        seen.add(document.id)
    missing = sorted(set(approved) - seen)
    if missing:
        raise DocumentError(f"Approved sources not fetched yet: {', '.join(missing)}")
    return documents


def render_document(document: SourceDocument) -> str:
    meta = {
        "id": document.id,
        "title": document.title,
        "publisher": document.publisher,
        "url": document.url,
        "license": document.license,
        "attribution": document.attribution,
        "source_last_updated": document.source_last_updated or "",
        "retrieved": document.retrieved or "",
    }
    header = "\n".join(f"{key}: {value}" for key, value in meta.items())
    body = "\n\n".join(f"## {section.heading}\n{section.text}" for section in document.sections)
    return f"---\n{header}\n---\n# {document.title}\n\n{body}\n"
