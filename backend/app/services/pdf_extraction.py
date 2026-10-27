"""PDF validation and text extraction.

Uploaded bytes are processed in memory and never written to disk. Extraction sits behind the
`TextExtractor` protocol so an OCR extractor can be added later without changing the API layer.
"""

from dataclasses import dataclass
from typing import Protocol

import pymupdf

PDF_MAGIC = b"%PDF-"
# Pages with fewer non-whitespace characters than this are treated as having no text layer.
MIN_CHARS_PER_TEXT_PAGE = 20


class PDFExtractionError(Exception):
    """Base class for extraction failures. `code` and `message` are safe to show to users."""

    code = "pdf_error"
    status_code = 422
    message = "The PDF could not be processed."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        if message:
            self.message = message


class EmptyFileError(PDFExtractionError):
    code = "empty_file"
    status_code = 400
    message = "The uploaded file is empty."


class NotAPDFError(PDFExtractionError):
    code = "invalid_file_type"
    status_code = 415
    message = "Only PDF files are supported."


class FileTooLargeError(PDFExtractionError):
    code = "file_too_large"
    status_code = 413


class UnreadablePDFError(PDFExtractionError):
    code = "unreadable_pdf"
    message = "The PDF appears to be damaged and could not be opened."


class EncryptedPDFError(PDFExtractionError):
    code = "encrypted_pdf"
    message = "The PDF is password-protected. Remove the password and upload it again."


class TooManyPagesError(PDFExtractionError):
    code = "too_many_pages"


class NoExtractableTextError(PDFExtractionError):
    code = "no_extractable_text"
    message = (
        "No readable text was found. The PDF may be a scanned image; scanned reports are not "
        "supported yet. Please upload a digitally generated PDF."
    )


@dataclass(frozen=True)
class PageText:
    page_number: int  # 1-based
    text: str

    @property
    def has_text(self) -> bool:
        return len("".join(self.text.split())) >= MIN_CHARS_PER_TEXT_PAGE


@dataclass(frozen=True)
class ExtractedDocument:
    page_count: int
    pages: list[PageText]
    method: str

    @property
    def text(self) -> str:
        return "\n\n".join(page.text for page in self.pages if page.text)

    @property
    def pages_without_text(self) -> list[int]:
        return [page.page_number for page in self.pages if not page.has_text]


class TextExtractor(Protocol):
    method: str

    def extract(self, data: bytes) -> ExtractedDocument: ...


def validate_pdf_bytes(data: bytes, *, max_bytes: int) -> None:
    """Cheap checks performed before the PDF parser touches the data."""
    if not data:
        raise EmptyFileError()
    if len(data) > max_bytes:
        raise FileTooLargeError(f"The file exceeds the {max_bytes // (1024 * 1024)} MB limit.")
    # The PDF header may be preceded by a little junk; the spec allows it within the first 1 KB.
    if PDF_MAGIC not in data[:1024]:
        raise NotAPDFError()


class PyMuPDFTextExtractor:
    """Extracts the embedded text layer from digitally generated PDFs."""

    method = "pymupdf_text_layer"

    def __init__(self, max_pages: int) -> None:
        self.max_pages = max_pages

    def extract(self, data: bytes) -> ExtractedDocument:
        try:
            document = pymupdf.open(stream=data, filetype="pdf")
        except (pymupdf.FileDataError, pymupdf.EmptyFileError, RuntimeError, ValueError) as exc:
            raise UnreadablePDFError() from exc

        with document:
            if document.needs_pass:
                raise EncryptedPDFError()
            if document.page_count == 0:
                raise UnreadablePDFError("The PDF has no pages.")
            if document.page_count > self.max_pages:
                raise TooManyPagesError(
                    f"The PDF has {document.page_count} pages; the limit is {self.max_pages}."
                )
            try:
                pages = [
                    PageText(page_number=index + 1, text=_normalize(page.get_text("text", sort=True)))
                    for index, page in enumerate(document)
                ]
            except RuntimeError as exc:
                raise UnreadablePDFError("The PDF content could not be read.") from exc

        extracted = ExtractedDocument(page_count=len(pages), pages=pages, method=self.method)
        if not any(page.has_text for page in pages):
            raise NoExtractableTextError()
        return extracted


def _normalize(text: str) -> str:
    """Trim trailing spaces and collapse runs of blank lines without altering line content."""
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    out: list[str] = []
    for line in lines:
        if line or (out and out[-1]):
            out.append(line)
    return "\n".join(out).strip()
