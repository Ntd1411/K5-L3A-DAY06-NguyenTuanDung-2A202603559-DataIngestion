"""Fast unit tests that do not require an API key or PostgreSQL."""
from __future__ import annotations

import unittest

from src.chunking import by_paragraph, fixed_size
from src.evaluation import evaluate_query, summarize
from src.ingestion import normalize_text
from src.models import DocumentPage
from src.store import PgVectorStore


class IngestionTests(unittest.TestCase):
    def test_normalize_text_preserves_paragraphs(self) -> None:
        raw = "  Học\tphí  \r\n\r\n\r\n  Đăng ký   học phần "
        result = normalize_text(raw)
        self.assertEqual(result, "Học phí\n\nĐăng ký học phần")


class ChunkingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.page = DocumentPage("doc", "source.pdf", 7, "", {"year": 2025})

    def test_fixed_size_overlap_and_stable_ids(self) -> None:
        self.page.text = "abcdefghij"
        first = fixed_size(self.page, size=6, overlap=2)
        second = fixed_size(self.page, size=6, overlap=2)
        self.assertEqual([chunk.text for chunk in first], ["abcdef", "efghij"])
        self.assertEqual([chunk.chunk_id for chunk in first], [chunk.chunk_id for chunk in second])
        self.assertEqual(first[0].metadata["year"], 2025)

    def test_fixed_size_rejects_invalid_overlap(self) -> None:
        self.page.text = "text"
        with self.assertRaises(ValueError):
            fixed_size(self.page, size=4, overlap=4)

    def test_paragraph_chunks_respect_maximum(self) -> None:
        self.page.text = "Đoạn thứ nhất.\n\nĐoạn thứ hai dài hơn.\n\n" + "x" * 30
        chunks = by_paragraph(self.page, max_size=25)
        self.assertTrue(chunks)
        self.assertTrue(all(len(chunk.text) <= 25 for chunk in chunks))
        self.assertTrue(all(chunk.page == 7 for chunk in chunks))


class EvaluationTests(unittest.TestCase):
    def test_evidence_requires_source_page_and_text(self) -> None:
        question = {
            "id": "q1",
            "split": "test",
            "question": "Hạn đăng ký là khi nào?",
            "gold_source_id": "handbook",
            "gold_page": 10,
            "evidence_quote": "Trước ngày 15 tháng 8",
        }
        hits = [
            {
                "document_id": "handbook",
                "page": 9,
                "text": "Trước ngày 15 tháng 8",
            },
            {
                "document_id": "handbook",
                "page": 10,
                "text": "Sinh viên đăng ký trước ngày 15\ntháng 8.",
            },
        ]
        trace = evaluate_query(question, hits)
        self.assertFalse(trace["hit_at_1"])
        self.assertTrue(trace["hit_at_3"])

        trace["strategy"] = "A"
        report = summarize([trace])
        group = report["groups"][0]
        self.assertEqual(group["hit_at_1"]["hits"], 0)
        self.assertEqual(group["evidence_hit_at_3"]["hits"], 1)


class StoreValidationTests(unittest.TestCase):
    def test_dimension_validation_does_not_need_database(self) -> None:
        store = PgVectorStore("postgresql://example", dimensions=3)
        with self.assertRaises(ValueError):
            store.search("A", [1.0, 2.0], top_k=3)


if __name__ == "__main__":
    unittest.main()
