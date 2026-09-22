from __future__ import annotations

import unittest
from typing import Self

from src.retrieval import search_knowledge_base


class FakeOllamaClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def embed(self, *, model: str, input: str) -> dict:
        self.calls.append({"model": model, "input": input})
        return {"embeddings": [[0.1, 0.2, 0.3]]}


class FakeLegacyOllamaClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def embeddings(self, *, model: str, prompt: str) -> dict:
        self.calls.append({"model": model, "prompt": prompt})
        return {"embedding": [0.1, 0.2, 0.3]}


class FakeCursor:
    def __init__(self, rows: list[tuple]) -> None:
        self.rows = rows
        self.sql = ""
        self.params: tuple | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, sql: str, params: tuple) -> None:
        self.sql = sql
        self.params = params

    def fetchall(self) -> list[tuple]:
        return self.rows


class FakeConnection:
    def __init__(self, rows: list[tuple]) -> None:
        self.fake_cursor = FakeCursor(rows)
        self.closed = False

    def cursor(self) -> FakeCursor:
        return self.fake_cursor

    def close(self) -> None:
        self.closed = True


class RetrievalTests(unittest.TestCase):
    def test_returns_ranked_chunks_and_source_metadata(self) -> None:
        rows = [
            (
                "chunk-1",
                "doc-1",
                "Mixture-of-experts activates selected experts per token.",
                {
                    "title": "MoE Systems",
                    "canonical_url": "https://example.org/moe",
                    "topic": "experts",
                },
                0.2166,
            )
        ]
        client = FakeOllamaClient()
        connection = FakeConnection(rows)

        results = search_knowledge_base(
            "  How do MoE models reduce computation?  ",
            top_k=3,
            embedding_model="qwen3-embedding:8b",
            ollama_client=client,
            connection=connection,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["rank"], 1)
        self.assertEqual(results[0]["chunk_id"], "chunk-1")
        self.assertEqual(results[0]["source_url"], "https://example.org/moe")
        self.assertEqual(results[0]["distance"], 0.2166)
        self.assertEqual(
            client.calls[0]["input"], "How do MoE models reduce computation?"
        )
        self.assertIn("embedding <=> %s::vector", connection.fake_cursor.sql)
        self.assertEqual(connection.fake_cursor.params[1], 3)
        self.assertFalse(
            connection.closed, "Injected connections are owned by the caller"
        )

    def test_rejects_empty_query(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            search_knowledge_base(
                "   ",
                ollama_client=FakeOllamaClient(),
                connection=FakeConnection([]),
            )

    def test_supports_week_one_legacy_ollama_embedding_api(self) -> None:
        client = FakeLegacyOllamaClient()
        results = search_knowledge_base(
            "legacy endpoint test",
            ollama_client=client,
            connection=FakeConnection([]),
        )

        self.assertEqual(results, [])
        self.assertEqual(client.calls[0]["prompt"], "legacy endpoint test")

    def test_rejects_invalid_top_k(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 1 and 20"):
            search_knowledge_base(
                "test",
                top_k=21,
                ollama_client=FakeOllamaClient(),
                connection=FakeConnection([]),
            )


if __name__ == "__main__":
    unittest.main()
