"""Read PDF pages while preserving enough information to trace every chunk."""
from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader

from .models import DocumentPage


LOGGER = logging.getLogger(__name__)


def load_pdf(
    path: Path,
    document_id: str,
    source: str,
    metadata: dict[str, object] | None = None,
) -> list[DocumentPage]:
    """Extract physical PDF pages and keep one-based page numbers.

    Empty pages are returned instead of silently discarded so the caller can audit
    extraction failures. OCR is deliberately not attempted here.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF not found: {path}")
    if not document_id.strip():
        raise ValueError("document_id must not be empty")

    reader = PdfReader(path)
    pages: list[DocumentPage] = []
    base_metadata = dict(metadata or {})
    for page_number, pdf_page in enumerate(reader.pages, start=1):
        try:
            raw_text = pdf_page.extract_text() or ""
        except Exception as exc:  # pypdf raises several parser-specific errors
            LOGGER.warning("Could not extract %s page %d: %s", path, page_number, exc)
            raw_text = ""
        text = normalize_text(raw_text)
        page_metadata = dict(base_metadata)
        page_metadata["extraction_status"] = "ok" if text else "empty"
        if not text:
            LOGGER.warning("No extractable text on %s page %d", path, page_number)
        pages.append(
            DocumentPage(
                document_id=document_id,
                source=source,
                page=page_number,
                text=text,
                metadata=page_metadata,
            )
        )
    return pages


def normalize_text(text: str) -> str:
    """Normalize Unicode/whitespace while retaining paragraph boundaries."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ")
    # Collapse horizontal whitespace, but keep newlines for paragraph chunking.
    lines = [re.sub(r"[\t\f\v ]+", " ", line).strip() for line in text.split("\n")]
    normalized = "\n".join(lines)
    normalized = re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", normalized)
    return normalized.strip()
