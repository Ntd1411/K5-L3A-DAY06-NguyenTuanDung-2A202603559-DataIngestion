"""Evaluate retrieval evidence and preserve auditable per-query traces."""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Any


def _normalized(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    return re.sub(r"\s+", " ", text).strip()


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return [value]


def _gold_candidates(question: dict[str, Any]) -> list[dict[str, Any]]:
    """Return explicit gold alternatives, or expand the simple benchmark fields."""
    alternatives = question.get("gold_evidence")
    if alternatives:
        if not isinstance(alternatives, list) or not all(
            isinstance(item, dict) for item in alternatives
        ):
            raise ValueError("gold_evidence must be a list of objects")
        candidates = alternatives
    else:
        required = ("gold_source_id", "gold_page", "evidence_quote")
        missing = [field for field in required if question.get(field) in (None, "", [])]
        if missing:
            raise ValueError(f"Question {question.get('id', '?')} missing gold fields: {missing}")
        candidates = [
            {"source_id": source, "page": page, "evidence_quote": evidence}
            for source in _as_list(question["gold_source_id"])
            for page in _as_list(question["gold_page"])
            for evidence in _as_list(question["evidence_quote"])
        ]

    normalized_candidates = []
    for candidate in candidates:
        source_id = candidate.get("source_id", candidate.get("gold_source_id"))
        page = candidate.get("page", candidate.get("gold_page"))
        evidence = candidate.get("evidence_quote")
        if source_id in (None, "") or page in (None, "") or evidence in (None, ""):
            raise ValueError(f"Invalid gold evidence for question {question.get('id', '?')}")
        normalized_candidates.append(
            {"source_id": str(source_id), "page": int(page), "evidence": _normalized(evidence)}
        )
    return normalized_candidates


def _is_evidence_hit(hit: dict[str, Any], candidates: list[dict[str, Any]]) -> bool:
    hit_text = _normalized(hit.get("text", ""))
    return any(
        str(hit.get("document_id")) == candidate["source_id"]
        and int(hit.get("page", -1)) == candidate["page"]
        and candidate["evidence"] in hit_text
        for candidate in candidates
    )


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    """Check source, page, and evidence containment for top-1/top-3.

    This deliberately does not infer human coherence or grounding labels.
    """
    if not question.get("id") or not question.get("question"):
        raise ValueError("Each benchmark question needs id and question")
    candidates = _gold_candidates(question)
    annotated_hits = []
    for rank, hit in enumerate(hits[:3], start=1):
        annotated = dict(hit)
        annotated["rank"] = rank
        annotated["evidence_hit"] = _is_evidence_hit(hit, candidates)
        annotated_hits.append(annotated)
    return {
        "question_id": question["id"],
        "split": question.get("split", "unknown"),
        "question": question["question"],
        "expected_answer": question.get("expected_answer"),
        "filter": question.get("filter"),
        "hit_at_1": bool(annotated_hits and annotated_hits[0]["evidence_hit"]),
        "hit_at_3": any(hit["evidence_hit"] for hit in annotated_hits),
        "hits": annotated_hits,
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate numerator, denominator, and rate by strategy/split."""
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for trace in traces:
        grouped[(trace.get("strategy", "unknown"), trace.get("split", "unknown"))].append(
            trace
        )

    groups = []
    for (strategy, split), items in sorted(grouped.items()):
        total = len(items)
        hit1 = sum(bool(item.get("hit_at_1")) for item in items)
        hit3 = sum(bool(item.get("hit_at_3")) for item in items)
        groups.append(
            {
                "strategy": strategy,
                "split": split,
                "questions": total,
                "hit_at_1": {"hits": hit1, "total": total, "rate": hit1 / total},
                "evidence_hit_at_3": {"hits": hit3, "total": total, "rate": hit3 / total},
            }
        )
    return {"groups": groups}
