"""Adapters for real local or API embedding models."""
from __future__ import annotations

import json
import os
import time
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, question: str) -> list[float]: ...


class MyEmbedder:
    """Use one real model through local, OpenAI, OpenRouter, Gemini, or Voyage."""

    _KNOWN_DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }

    def __init__(self, model_name: str) -> None:
        if not model_name.strip():
            raise ValueError("EMBEDDING_MODEL must be configured")
        self.model_name = model_name.removeprefix("local:")
        configured_provider = os.getenv("EMBEDDING_PROVIDER", "").strip().lower()
        self.provider = configured_provider or self._infer_provider(model_name)
        # Some free OpenRouter routes accept only one non-trivial text per call;
        # other providers support efficient batches.
        default_batch_size = "1" if self.provider == "openrouter" else "64"
        self.batch_size = int(os.getenv("EMBEDDING_BATCH_SIZE", default_batch_size))
        if self.batch_size <= 0:
            raise ValueError("EMBEDDING_BATCH_SIZE must be positive")
        self.request_count = 0
        self._last_request_started = 0.0
        self._local_model: Any = None
        configured_dimensions = os.getenv("EMBEDDING_DIMENSIONS", "").strip()
        self._dimensions = int(configured_dimensions) if configured_dimensions else None

        if self.provider == "local":
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError(
                    "Local embeddings require: pip install sentence-transformers"
                ) from exc
            self._local_model = SentenceTransformer(self.model_name)
            self._dimensions = int(self._local_model.get_sentence_embedding_dimension())
        elif self.provider == "openai":
            self.api_key = self._required_env("OPENAI_API_KEY")
            self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
            self._dimensions = self._dimensions or self._KNOWN_DIMENSIONS.get(self.model_name)
        elif self.provider == "openrouter":
            self.api_key = self._required_env("OPENROUTER_API_KEY")
            self.base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
        elif self.provider == "gemini":
            self.api_key = self._required_env("GEMINI_API_KEY")
            self.base_url = os.getenv(
                "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
            ).rstrip("/")
        elif self.provider == "voyage":
            self.api_key = self._required_env("VOYAGE_API_KEY")
            self.base_url = os.getenv(
                "VOYAGE_BASE_URL", "https://api.voyageai.com/v1"
            ).rstrip("/")
            if self.model_name.startswith("voyage-4"):
                self._dimensions = self._dimensions or 1024
        else:
            raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {self.provider}")

        # pgvector requires a dimension before the table is created. Probe unknown
        # API models once rather than guessing a provider-specific value.
        if self._dimensions is None:
            self._dimensions = len(self._embed_batch(["embedding dimension probe"], "document")[0])
        if self._dimensions <= 0:
            raise ValueError("Embedding dimension must be positive")

    @property
    def dimensions(self) -> int:
        return int(self._dimensions)

    @staticmethod
    def _infer_provider(model_name: str) -> str:
        if model_name.startswith("local:"):
            return "local"
        if os.getenv("OPENAI_API_KEY"):
            return "openai"
        if os.getenv("OPENROUTER_API_KEY"):
            return "openrouter"
        if os.getenv("GEMINI_API_KEY"):
            return "gemini"
        if os.getenv("VOYAGE_API_KEY"):
            return "voyage"
        raise ValueError(
            "Set EMBEDDING_PROVIDER and its API key, or use EMBEDDING_MODEL=local:<model>"
        )

    @staticmethod
    def _required_env(name: str) -> str:
        value = os.getenv(name, "").strip()
        if not value:
            raise ValueError(f"{name} is required for the selected embedding provider")
        return value

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed_many(texts, "document")

    def embed_query(self, question: str) -> list[float]:
        if not question.strip():
            raise ValueError("question must not be empty")
        return self._embed_many([question], "query")[0]

    def embed_queries(self, questions: list[str]) -> list[list[float]]:
        """Batch query embeddings when the provider supports batching."""
        return self._embed_many(questions, "query")

    def _embed_many(self, texts: list[str], task: str) -> list[list[float]]:
        if not texts:
            return []
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("Embedding inputs must be non-empty strings")
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            vectors.extend(self._embed_batch(texts[start : start + self.batch_size], task))
        if len(vectors) != len(texts):
            raise RuntimeError("Embedding provider returned a different number of vectors")
        for vector in vectors:
            if len(vector) != self.dimensions:
                raise RuntimeError(
                    f"Expected {self.dimensions} dimensions, received {len(vector)}"
                )
        return vectors

    def _embed_batch(self, texts: list[str], task: str) -> list[list[float]]:
        if self.provider == "local":
            values = self._local_model.encode(
                texts, normalize_embeddings=True, show_progress_bar=False
            )
            return [[float(value) for value in vector] for vector in values]
        if self.provider in {"openai", "openrouter"}:
            return self._embed_openai_compatible(texts)
        if self.provider == "voyage":
            return self._embed_voyage(texts, task)
        return self._embed_gemini(texts, task)

    def _embed_openai_compatible(self, texts: list[str]) -> list[list[float]]:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if self.provider == "openrouter":
            headers.update({"HTTP-Referer": "http://localhost", "X-Title": "Day 06 Lab"})
        payload: dict[str, Any] = {"model": self.model_name, "input": texts}
        if os.getenv("EMBEDDING_DIMENSIONS") and self.model_name.startswith("text-embedding-3"):
            payload["dimensions"] = self.dimensions
        response = self._request_json(f"{self.base_url}/embeddings", payload, headers)
        data = sorted(response.get("data", []), key=lambda item: item.get("index", 0))
        return [[float(value) for value in item["embedding"]] for item in data]

    def _embed_gemini(self, texts: list[str], task: str) -> list[list[float]]:
        model_path = self.model_name if self.model_name.startswith("models/") else f"models/{self.model_name}"
        task_type = "RETRIEVAL_QUERY" if task == "query" else "RETRIEVAL_DOCUMENT"
        requests = []
        for text in texts:
            item: dict[str, Any] = {
                "model": model_path,
                "content": {"parts": [{"text": text}]},
                "taskType": task_type,
            }
            if os.getenv("EMBEDDING_DIMENSIONS"):
                item["outputDimensionality"] = self.dimensions
            requests.append(item)
        url = f"{self.base_url}/{quote(model_path, safe='/')}:batchEmbedContents?key={quote(self.api_key)}"
        response = self._request_json(url, {"requests": requests})
        return [
            [float(value) for value in embedding["values"]]
            for embedding in response.get("embeddings", [])
        ]

    def _embed_voyage(self, texts: list[str], task: str) -> list[list[float]]:
        payload: dict[str, Any] = {
            "input": texts,
            "model": self.model_name,
            "input_type": "query" if task == "query" else "document",
            "truncation": False,
        }
        if os.getenv("EMBEDDING_DIMENSIONS"):
            payload["output_dimension"] = self.dimensions
        response = self._request_json(
            f"{self.base_url}/embeddings",
            payload,
            {"Authorization": f"Bearer {self.api_key}"},
        )
        data = sorted(response.get("data", []), key=lambda item: item.get("index", 0))
        return [[float(value) for value in item["embedding"]] for item in data]

    def _request_json(
        self, url: str, payload: dict[str, Any], headers: dict[str, str] | None = None
    ) -> dict[str, Any]:
        request_headers = {"Content-Type": "application/json", **(headers or {})}
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=request_headers,
            method="POST",
        )
        self.request_count += 1
        retryable_statuses = {429, 500, 502, 503, 504}
        max_attempts = int(os.getenv("EMBEDDING_MAX_ATTEMPTS", "4"))
        default_interval = "21" if self.provider == "voyage" else "0"
        min_interval = float(
            os.getenv("EMBEDDING_MIN_REQUEST_INTERVAL", default_interval)
        )
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            elapsed = time.monotonic() - self._last_request_started
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            self._last_request_started = time.monotonic()
            try:
                with urlopen(request, timeout=60) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:500]
                last_error = RuntimeError(
                    f"Embedding API returned HTTP {exc.code}: {detail}"
                )
                if exc.code not in retryable_statuses or attempt == max_attempts:
                    raise last_error from exc
            except (URLError, TimeoutError) as exc:
                last_error = RuntimeError(f"Embedding API request failed: {exc}")
                if attempt == max_attempts:
                    raise last_error from exc
            time.sleep(min(2 ** (attempt - 1), 8))
        raise RuntimeError(f"Embedding API failed after retries: {last_error}")
