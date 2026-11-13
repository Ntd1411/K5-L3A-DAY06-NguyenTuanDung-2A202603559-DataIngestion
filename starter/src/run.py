"""Command-line entry point for ingestion, retrieval, and benchmark evaluation."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import statistics
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .chunking import by_paragraph, fixed_size
from .embeddings import MyEmbedder
from .evaluation import evaluate_query, summarize
from .ingestion import load_pdf
from .models import Chunk, DocumentPage
from .store import PgVectorStore


STARTER_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = STARTER_DIR.parent


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Day 06 data-ingestion pipeline")
    parser.add_argument("--pdf", type=Path, default=STARTER_DIR / "data/so-tay-sinh-vien.pdf")
    parser.add_argument("--document-id", default="so-tay-sinh-vien")
    parser.add_argument("--source", help="Traceable source label; defaults to the PDF path")
    parser.add_argument(
        "--page-metadata",
        type=Path,
        help="Optional JSON with 'defaults' and per-page metadata under 'pages'",
    )
    parser.add_argument(
        "--benchmark", type=Path, default=REPO_DIR / "benchmark/questions.json"
    )
    parser.add_argument("--results", type=Path, default=STARTER_DIR / "results")
    parser.add_argument("--fixed-size", type=int, default=500)
    parser.add_argument("--overlap", type=int, default=50)
    parser.add_argument("--paragraph-max-size", type=int, default=800)
    parser.add_argument("--min-content-pages", type=int, default=30)
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Stop after extraction/chunking; no API, database, or benchmark required",
    )
    return parser


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Required JSON file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_metadata(path: Path | None) -> tuple[dict[str, Any], dict[int, dict[str, Any]]]:
    if path is None:
        return {}, {}
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise ValueError("Page metadata must be a JSON object")
    defaults = payload.get("defaults", {})
    raw_pages = payload.get("pages", {})
    if not isinstance(defaults, dict) or not isinstance(raw_pages, dict):
        raise ValueError("Page metadata 'defaults' and 'pages' must be objects")
    pages: dict[int, dict[str, Any]] = {}
    for page, metadata in raw_pages.items():
        if not isinstance(metadata, dict):
            raise ValueError(f"Metadata for page {page} must be an object")
        pages[int(page)] = metadata
    return defaults, pages


def _apply_page_metadata(
    pages: list[DocumentPage], per_page: dict[int, dict[str, Any]]
) -> None:
    known_pages = {page.page for page in pages}
    unknown = set(per_page) - known_pages
    if unknown:
        raise ValueError(f"Metadata refers to nonexistent PDF pages: {sorted(unknown)}")
    for page in pages:
        page.metadata.update(per_page.get(page.page, {}))


def _chunk_stats(chunks: list[Chunk]) -> dict[str, Any]:
    lengths = [len(chunk.text) for chunk in chunks]
    if not lengths:
        return {"chunk_count": 0, "total_characters": 0}
    return {
        "chunk_count": len(chunks),
        "total_characters": sum(lengths),
        "min_characters": min(lengths),
        "median_characters": statistics.median(lengths),
        "mean_characters": round(statistics.mean(lengths), 2),
        "max_characters": max(lengths),
    }


def _load_benchmark(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    questions = payload.get("questions") if isinstance(payload, dict) else payload
    if not isinstance(questions, list) or not all(isinstance(item, dict) for item in questions):
        raise ValueError("Benchmark must be a JSON list or an object containing 'questions'")
    ids = [question.get("id") for question in questions]
    if any(not question_id for question_id in ids) or len(ids) != len(set(ids)):
        raise ValueError("Benchmark question IDs must be non-empty and unique")
    dev = sum(question.get("split") == "dev" for question in questions)
    test = sum(question.get("split") == "test" for question in questions)
    invalid_splits = {question.get("split") for question in questions} - {"dev", "test"}
    filtered = [question for question in questions if question.get("filter")]
    filtered_test = [question for question in filtered if question.get("split") == "test"]
    if len(questions) < 20 or dev < 15 or test < 5:
        raise ValueError(
            f"Benchmark needs >=20 questions with >=15 dev and >=5 test; got {len(questions)}, {dev}, {test}"
        )
    if invalid_splits:
        raise ValueError(f"Only dev/test splits are allowed: {sorted(map(str, invalid_splits))}")
    if len(filtered) < 3 or not filtered_test:
        raise ValueError("Benchmark needs >=3 filter questions, including >=1 test question")
    for question in questions:
        if not isinstance(question.get("question"), str) or not question["question"].strip():
            raise ValueError(f"Question {question.get('id')} has no question text")
        if question.get("filter") is not None and not isinstance(question["filter"], dict):
            raise ValueError(f"Question {question.get('id')} filter must be an object")
    return questions


def _preview(chunks: list[Chunk], count: int = 5) -> list[dict[str, Any]]:
    return [
        {
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "source": chunk.source,
            "page": chunk.page,
            "text": chunk.text,
            "metadata": chunk.metadata,
        }
        for chunk in chunks[:count]
    ]


def _embedding_cache_key(embedder: MyEmbedder, task: str, text: str) -> str:
    identity = f"{embedder.provider}\0{embedder.model_name}\0{embedder.dimensions}\0{task}\0{text}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _embed_with_cache(
    embedder: MyEmbedder,
    texts: list[str],
    task: str,
    cache_dir: Path,
) -> tuple[list[list[float]], dict[str, int]]:
    """Persist each successful embedding so interrupted API runs can resume."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    vectors: list[list[float] | None] = [None] * len(texts)
    missing: list[tuple[int, str, Path]] = []
    cache_hits = 0
    for index, text in enumerate(texts):
        path = cache_dir / f"{_embedding_cache_key(embedder, task, text)}.json"
        if path.is_file():
            try:
                vector = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(vector, list) and len(vector) == embedder.dimensions:
                    vectors[index] = [float(value) for value in vector]
                    cache_hits += 1
                    continue
            except (OSError, ValueError, json.JSONDecodeError):
                pass
        missing.append((index, text, path))

    for start in range(0, len(missing), embedder.batch_size):
        batch = missing[start : start + embedder.batch_size]
        batch_texts = [item[1] for item in batch]
        batch_vectors = (
            embedder.embed_queries(batch_texts)
            if task == "query"
            else embedder.embed_documents(batch_texts)
        )
        for (index, _text, path), vector in zip(batch, batch_vectors, strict=True):
            vectors[index] = vector
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(vector), encoding="utf-8")
            temporary.replace(path)

    if any(vector is None for vector in vectors):
        raise RuntimeError("Embedding cache failed to populate all vectors")
    return [vector for vector in vectors if vector is not None], {
        "cache_hits": cache_hits,
        "api_embeddings": len(missing),
    }


def main() -> None:
    args = _parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    load_dotenv(STARTER_DIR / ".env")
    started = time.perf_counter()

    defaults, page_metadata = _load_metadata(args.page_metadata)
    if args.source:
        source = args.source
    else:
        try:
            source = str(args.pdf.resolve().relative_to(REPO_DIR.resolve()))
        except ValueError:
            source = str(args.pdf)
    pages = load_pdf(args.pdf, args.document_id, source, metadata=defaults)
    _apply_page_metadata(pages, page_metadata)
    content_pages = [page for page in pages if page.text]
    empty_pages = [page.page for page in pages if not page.text]
    if len(content_pages) < args.min_content_pages:
        raise ValueError(
            f"Only {len(content_pages)} pages contain extractable text; "
            f"at least {args.min_content_pages} are required"
        )

    chunks_a = [
        chunk
        for page in content_pages
        for chunk in fixed_size(page, args.fixed_size, args.overlap)
    ]
    chunks_b = [
        chunk
        for page in content_pages
        for chunk in by_paragraph(page, args.paragraph_max_size)
    ]
    extraction_seconds = time.perf_counter() - started
    stats: dict[str, Any] = {
        "document_id": args.document_id,
        "source": source,
        "physical_pages": len(pages),
        "pages_with_extractable_text": len(content_pages),
        "empty_or_unreadable_pages": empty_pages,
        "manual_check_required": "Confirm which extracted pages count as useful content.",
        "strategies": {
            "A": {
                "chunking": "fixed_size",
                "size": args.fixed_size,
                "overlap": args.overlap,
                **_chunk_stats(chunks_a),
            },
            "B": {
                "chunking": "paragraph",
                "max_size": args.paragraph_max_size,
                **_chunk_stats(chunks_b),
            },
            "C": {
                "chunking": "paragraph",
                "max_size": args.paragraph_max_size,
                "metadata_filter": True,
                **_chunk_stats(chunks_b),
            },
        },
        "extraction_and_chunking_seconds": round(extraction_seconds, 4),
    }
    _write_json(args.results / "ingestion_stats.json", stats)
    _write_json(
        args.results / "chunk_preview.json",
        {"A": _preview(chunks_a), "B_and_C": _preview(chunks_b)},
    )
    logging.info(
        "Extracted %d/%d pages; built %d fixed and %d paragraph chunks",
        len(content_pages),
        len(pages),
        len(chunks_a),
        len(chunks_b),
    )
    if args.prepare_only:
        logging.info("Prepare-only complete. Results: %s", args.results)
        return

    questions = _load_benchmark(args.benchmark)
    model_name = os.getenv("EMBEDDING_MODEL", "").strip()
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not model_name:
        raise ValueError("EMBEDDING_MODEL is missing from starter/.env")
    if not database_url:
        raise ValueError("DATABASE_URL is missing from starter/.env")

    embedder = MyEmbedder(model_name)
    store = PgVectorStore(database_url, embedder.dimensions)
    store.create_schema()
    ingestion_timings: dict[str, float] = {}

    embed_started = time.perf_counter()
    cache_dir = args.results / "embedding_cache"
    vectors_a, cache_a = _embed_with_cache(
        embedder, [chunk.text for chunk in chunks_a], "document", cache_dir
    )
    ingestion_timings["embed_A_seconds"] = round(time.perf_counter() - embed_started, 4)
    embed_started = time.perf_counter()
    vectors_b, cache_b = _embed_with_cache(
        embedder, [chunk.text for chunk in chunks_b], "document", cache_dir
    )
    ingestion_timings["embed_B_and_C_seconds"] = round(time.perf_counter() - embed_started, 4)
    for strategy, chunks, vectors in (
        ("A", chunks_a, vectors_a),
        ("B", chunks_b, vectors_b),
        ("C", chunks_b, vectors_b),
    ):
        store_started = time.perf_counter()
        store.upsert(strategy, chunks, vectors)
        ingestion_timings[f"store_{strategy}_seconds"] = round(
            time.perf_counter() - store_started, 4
        )

    question_vectors, cache_queries = _embed_with_cache(
        embedder,
        [str(question["question"]) for question in questions],
        "query",
        cache_dir,
    )
    traces = []
    for question, query_vector in zip(questions, question_vectors, strict=True):
        for strategy in ("A", "B", "C"):
            filters = question.get("filter") if strategy == "C" else None
            hits = store.search(strategy, query_vector, top_k=3, filters=filters)
            trace = evaluate_query(question, hits)
            trace["strategy"] = strategy
            trace["filter_applied"] = filters or None
            traces.append(trace)

    summary = summarize(traces)
    summary["model"] = {
        "provider": embedder.provider,
        "name": embedder.model_name,
        "dimensions": embedder.dimensions,
        "api_requests": embedder.request_count,
    }
    summary["ingestion_timings"] = ingestion_timings
    summary["embedding_cache"] = {
        "strategy_A": cache_a,
        "strategies_B_and_C": cache_b,
        "queries": cache_queries,
    }
    summary["total_pipeline_seconds"] = round(time.perf_counter() - started, 4)
    _write_json(args.results / "retrieval_traces.json", traces)
    _write_json(args.results / "summary.json", summary)
    logging.info("Pipeline complete. Results: %s", args.results)


if __name__ == "__main__":
    main()
