"""Heuristic detection of instruction-like text inside uploaded documents.

Detection only produces a warning; the text is never executed or obeyed. Prompts built in later
milestones also delimit report text as untrusted data, so this check is one layer, not the defence.
"""

import re

from app.services.pdf_extraction import PageText

INJECTION_PATTERNS = [
    r"\bignore\s+(?:all\s+|any\s+)?(?:the\s+)?(?:previous|prior|above|earlier)\s+(?:instructions|prompts?|rules)",
    r"\bdisregard\s+(?:all\s+|the\s+)?(?:previous|prior|above|system)\b",
    r"\b(?:system|developer)\s+prompt\b",
    r"\byou\s+are\s+now\b",
    r"\bact\s+as\s+(?:an?\s+)?(?:different|new|unrestricted)\b",
    r"\b(?:new|updated)\s+instructions?\s*:",
    r"\breveal\s+(?:your|the)\s+(?:instructions|prompt|api\s*key)",
    r"\bdo\s+not\s+(?:mention|include|show)\s+(?:the\s+)?(?:disclaimer|warning)",
]
_INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)


def find_instruction_like_pages(pages: list[PageText]) -> list[int]:
    """Return 1-based page numbers containing text that looks like instructions to an AI."""
    return [page.page_number for page in pages if _INJECTION_RE.search(page.text)]
