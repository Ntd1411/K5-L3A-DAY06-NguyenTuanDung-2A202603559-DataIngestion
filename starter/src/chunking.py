"""Fixed-size and paragraph-aware chunking strategies."""
from __future__ import annotations

import hashlib
import re

from .models import Chunk, DocumentPage


def _chunk_id(page: DocumentPage, method: str, index: int, text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"{page.document_id}:p{page.page}:{method}:{index:04d}:{digest}"


def _make_chunk(page: DocumentPage, method: str, index: int, text: str) -> Chunk:
    metadata = dict(page.metadata)
    metadata.update({"chunking": method, "chunk_index": index})
    return Chunk(
        chunk_id=_chunk_id(page, method, index, text),
        document_id=page.document_id,
        source=page.source,
        page=page.page,
        text=text,
        metadata=metadata,
    )


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    """Split a page into overlapping character windows."""
    if size <= 0:
        raise ValueError("size must be positive")
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must satisfy 0 <= overlap < size")
    if not page.text.strip():
        return []

    chunks: list[Chunk] = []
    start = 0
    index = 0
    while start < len(page.text):
        end = min(start + size, len(page.text))
        text = page.text[start:end].strip()
        if text:
            chunks.append(_make_chunk(page, "fixed", index, text))
            index += 1
        if end == len(page.text):
            break
        start = end - overlap
    return chunks


def _split_oversized(text: str, max_size: int) -> list[str]:
    """Split long paragraphs near sentence/word boundaries when possible."""
    pieces: list[str] = []
    remaining = text.strip()
    while len(remaining) > max_size:
        window = remaining[: max_size + 1]
        candidates = [
            window.rfind(". "),
            window.rfind("? "),
            window.rfind("! "),
            window.rfind("; "),
            window.rfind(" "),
        ]
        cut = max(candidates)
        # Avoid producing a tiny piece merely because an early boundary exists.
        if cut < max_size // 2:
            cut = max_size
        elif window[cut : cut + 2] in {". ", "? ", "! ", "; "}:
            cut += 1
        piece = remaining[:cut].strip()
        if piece:
            pieces.append(piece)
        remaining = remaining[cut:].strip()
    if remaining:
        pieces.append(remaining)
    return pieces


_STRUCTURE_START = re.compile(
    r"^(?:[-•]\s+|[a-zđ]\)\s+|\d+(?:\.\d+)*[.)]\s+)", re.IGNORECASE
)


def _logical_paragraphs(text: str) -> list[str]:
    """Recover paragraphs from PDF lines when blank-line structure is absent."""
    paragraphs: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        current: list[str] = []
        for raw_line in block.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            is_short_heading = len(line) <= 120 and line.isupper() and any(
                character.isalpha() for character in line
            )
            starts_structure = bool(_STRUCTURE_START.match(line)) or is_short_heading
            if current and starts_structure:
                paragraphs.append("\n".join(current))
                current = []
            current.append(line)
        if current:
            paragraphs.append("\n".join(current))
    return paragraphs


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    """Group complete paragraphs up to ``max_size`` characters."""
    if max_size <= 0:
        raise ValueError("max_size must be positive")
    if not page.text.strip():
        return []

    paragraphs = _logical_paragraphs(page.text)
    units: list[str] = []
    for paragraph in paragraphs:
        units.extend(_split_oversized(paragraph, max_size))

    grouped: list[str] = []
    current = ""
    for unit in units:
        candidate = unit if not current else f"{current}\n\n{unit}"
        if len(candidate) <= max_size:
            current = candidate
            continue
        if current:
            grouped.append(current)
        current = unit
    if current:
        grouped.append(current)

    return [_make_chunk(page, "paragraph", index, text) for index, text in enumerate(grouped)]
