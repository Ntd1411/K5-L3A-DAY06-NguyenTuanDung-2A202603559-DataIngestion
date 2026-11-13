"""Persistent vector storage and cosine search using PostgreSQL + pgvector."""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

import psycopg
from psycopg import sql

from .models import Chunk


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(format(float(value), ".12g") for value in vector) + "]"


class PgVectorStore:
    TABLE = "ingestion_chunks"
    FILTERABLE_METADATA = {
        "section",
        "year",
        "version",
        "category",
        "audience",
        "language",
        "effective_date",
        "document_type",
    }

    def __init__(self, database_url: str, dimensions: int) -> None:
        if not database_url.strip():
            raise ValueError("DATABASE_URL must not be empty")
        if dimensions <= 0 or dimensions > 16000:
            raise ValueError("dimensions must be between 1 and 16000")
        self.database_url = database_url
        self.dimensions = dimensions
        self.table = (
            self.TABLE
            if type(self).TABLE != PgVectorStore.TABLE
            else f"{self.TABLE}_{dimensions}"
        )

    def _connect(self) -> psycopg.Connection[Any]:
        return psycopg.connect(self.database_url)

    def create_schema(self) -> None:
        """Create a dimension-specific table and useful lookup indexes."""
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cursor.execute(
                sql.SQL(
                    """
                    CREATE TABLE IF NOT EXISTS {} (
                        strategy TEXT NOT NULL,
                        chunk_id TEXT NOT NULL,
                        document_id TEXT NOT NULL,
                        source TEXT NOT NULL,
                        page INTEGER NOT NULL CHECK (page > 0),
                        text TEXT NOT NULL,
                        metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                        embedding vector({}) NOT NULL,
                        PRIMARY KEY (strategy, chunk_id)
                    )
                    """
                ).format(sql.Identifier(self.table), sql.Literal(self.dimensions))
            )
            cursor.execute(
                """
                SELECT format_type(a.atttypid, a.atttypmod)
                FROM pg_attribute a
                JOIN pg_class c ON c.oid = a.attrelid
                WHERE c.relname = %s AND a.attname = 'embedding'
                """,
                (self.table,),
            )
            row = cursor.fetchone()
            expected = f"vector({self.dimensions})"
            if not row or row[0] != expected:
                raise RuntimeError(
                    f"Existing embedding column is {row[0] if row else 'missing'}, expected {expected}. "
                    "Use a matching model or recreate the lab table."
                )
            cursor.execute(
                sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} (strategy, document_id)").format(
                    sql.Identifier(f"{self.table}_strategy_document_idx"),
                    sql.Identifier(self.table),
                )
            )
            cursor.execute(
                sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} USING GIN (metadata)").format(
                    sql.Identifier(f"{self.table}_metadata_idx"), sql.Identifier(self.table)
                )
            )

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        """Replace each supplied document atomically, preventing stale chunks."""
        if not strategy.strip():
            raise ValueError("strategy must not be empty")
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        if not chunks:
            return
        for vector in vectors:
            if len(vector) != self.dimensions:
                raise ValueError(
                    f"Expected vector dimension {self.dimensions}, received {len(vector)}"
                )

        grouped: dict[str, list[tuple[Chunk, list[float]]]] = defaultdict(list)
        for chunk, vector in zip(chunks, vectors, strict=True):
            grouped[chunk.document_id].append((chunk, vector))

        insert_query = sql.SQL(
            """
            INSERT INTO {} (
                strategy, chunk_id, document_id, source, page, text, metadata, embedding
            ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::vector)
            ON CONFLICT (strategy, chunk_id) DO UPDATE SET
                document_id = EXCLUDED.document_id,
                source = EXCLUDED.source,
                page = EXCLUDED.page,
                text = EXCLUDED.text,
                metadata = EXCLUDED.metadata,
                embedding = EXCLUDED.embedding
            """
        ).format(sql.Identifier(self.table))

        with self._connect() as connection, connection.cursor() as cursor:
            for document_id, pairs in grouped.items():
                cursor.execute(
                    sql.SQL("DELETE FROM {} WHERE strategy = %s AND document_id = %s").format(
                        sql.Identifier(self.table)
                    ),
                    (strategy, document_id),
                )
                rows = [
                    (
                        strategy,
                        chunk.chunk_id,
                        chunk.document_id,
                        chunk.source,
                        chunk.page,
                        chunk.text,
                        json.dumps(chunk.metadata, ensure_ascii=False),
                        _vector_literal(vector),
                    )
                    for chunk, vector in pairs
                ]
                cursor.executemany(insert_query, rows)

    def search(
        self,
        strategy: str,
        query_vector: list[float],
        top_k: int = 3,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Apply trusted metadata filters, then rank by cosine similarity."""
        if len(query_vector) != self.dimensions:
            raise ValueError(
                f"Expected query dimension {self.dimensions}, received {len(query_vector)}"
            )
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        filters = filters or {}
        allowed = self.FILTERABLE_METADATA | {"document_id", "source", "page"}
        unsupported = set(filters) - allowed
        if unsupported:
            raise ValueError(f"Unsupported metadata filters: {sorted(unsupported)}")

        clauses = [sql.SQL("strategy = %s")]
        params: list[Any] = [strategy]
        metadata_filters: dict[str, Any] = {}
        for key, value in filters.items():
            if key in {"document_id", "source", "page"}:
                clauses.append(sql.SQL("{} = %s").format(sql.Identifier(key)))
                params.append(value)
            else:
                metadata_filters[key] = value
        if metadata_filters:
            clauses.append(sql.SQL("metadata @> %s::jsonb"))
            params.append(json.dumps(metadata_filters, ensure_ascii=False))

        vector = _vector_literal(query_vector)
        query = sql.SQL(
            """
            SELECT chunk_id, document_id, source, page, text, metadata,
                   1 - (embedding <=> %s::vector) AS score
            FROM {}
            WHERE {}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """
        ).format(sql.Identifier(self.table), sql.SQL(" AND ").join(clauses))
        all_params = [vector, *params, vector, top_k]
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(query, all_params)
            rows = cursor.fetchall()
        return [
            {
                "chunk_id": row[0],
                "document_id": row[1],
                "source": row[2],
                "page": row[3],
                "text": row[4],
                "metadata": row[5],
                "score": float(row[6]),
                "strategy": strategy,
            }
            for row in rows
        ]
