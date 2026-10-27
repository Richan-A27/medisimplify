"""Download approved MedlinePlus lab-test pages and save them as clean Markdown documents.

Usage (from backend/):  .venv/bin/python -m scripts.fetch_sources [--only ID ...]

Only URLs in knowledge_base/sources/manifest.json are fetched. Text is copied from the page's main
article (headings, paragraphs, list items) up to the References section; nothing is paraphrased.
Pages carrying third-party copyright notices are rejected.
"""

import argparse
import datetime as dt
import re
import sys
import time
import urllib.request

from bs4 import BeautifulSoup, Tag

from app.config import get_settings
from app.rag.documents import Section, SourceDocument, load_manifest, render_document

USER_AGENT = "MediSimplify/0.1 (academic project; reference-corpus builder)"
STOP_HEADINGS = {"references", "related health topics", "related medical tests"}
COPYRIGHT_MARKERS = ("A.D.A.M.", "American Society of Health-System Pharmacists")
REQUEST_DELAY_SECONDS = 1.0


def fetch_html(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - fixed https URLs
        return response.read().decode("utf-8")


def _block_text(element: Tag) -> list[str]:
    blocks: list[str] = []
    for node in element.find_all(["p", "li", "h3"]):
        if node.find_parent("li") is not None and node.name != "li":
            continue  # paragraphs inside list items are covered by the li
        text = " ".join(node.get_text(" ", strip=True).split())
        # Undo spaces introduced around inline links, e.g. "anemia , a" -> "anemia, a".
        text = re.sub(r"\s+([.,;:!?)])", r"\1", text).replace("( ", "(")
        if not text:
            continue
        if node.name == "li":
            text = f"- {text}"
        elif node.name == "h3":
            text = f"{text}:"
        blocks.append(text)
    return blocks


def parse_medlineplus(html: str, entry: dict[str, str], retrieved: str) -> SourceDocument:
    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article")
    if article is None or article.find("h1") is None:
        raise ValueError("main article not found")
    article_text = article.get_text(" ")
    if any(marker in article_text for marker in COPYRIGHT_MARKERS):
        raise ValueError("page contains third-party copyrighted content")

    sections: list[Section] = []
    for section in article.select("div.main section"):
        heading = section.find("h2")
        if heading is None:
            continue
        title = " ".join(heading.get_text(" ", strip=True).split())
        if title.lower() in STOP_HEADINGS:
            break
        text = "\n".join(_block_text(section))
        if text:
            sections.append(Section(title, text))
    if not sections:
        raise ValueError("no content sections found")

    updated = soup.find(id="lastupdate")
    return SourceDocument(
        id=entry["id"],
        title=" ".join(article.find("h1").get_text(" ", strip=True).split()),
        publisher=entry["publisher"],
        url=entry["url"],
        license=entry["license"],
        attribution=entry["attribution"],
        source_last_updated=updated.get_text(strip=True).removeprefix("Last updated").strip() if updated else None,
        retrieved=retrieved,
        sections=sections,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", help="Fetch only these source IDs")
    args = parser.parse_args()

    sources_dir = get_settings().knowledge_base_dir / "sources"
    out_dir = sources_dir / "documents"
    out_dir.mkdir(parents=True, exist_ok=True)
    retrieved = dt.date.today().isoformat()
    failures = 0

    for index, entry in enumerate(load_manifest(sources_dir).values()):
        if args.only and entry["id"] not in args.only:
            continue
        if index:
            time.sleep(REQUEST_DELAY_SECONDS)
        try:
            document = parse_medlineplus(fetch_html(entry["url"]), entry, retrieved)
        except Exception as exc:  # report and continue with the remaining sources
            failures += 1
            print(f"FAILED {entry['id']}: {exc}", file=sys.stderr)
            continue
        (out_dir / f"{document.id}.md").write_text(render_document(document), encoding="utf-8")
        print(f"saved {document.id}: {document.title} ({len(document.sections)} sections)")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
