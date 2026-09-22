from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from qubettera.agents.tools.retrieval_tool import knowledge_retrieval, retrieve_knowledge_base
from qubettera.agents.tools.search_tool import live_web_search
from qubettera.agents.tools.crawl_tool import deep_web_crawl
from qubettera.agents.search.base import SearchResult


class TestRetrievalTool(unittest.TestCase):
    def test_tool_metadata(self) -> None:
        self.assertEqual(knowledge_retrieval.name, "knowledge_retrieval")
        self.assertIn("knowledge base", knowledge_retrieval.description)
        self.assertEqual(retrieve_knowledge_base.name, "retrieve_knowledge_base")

    @patch("qubettera.agents.tools.retrieval_tool.retrieve")
    def test_successful_retrieval_returns_json_documents(self, mock_retrieve) -> None:
        mock_retrieve.return_value = [
            {
                "rank": 1,
                "text": "Mixture-of-Experts reduces FLOPs per token.",
                "title": "MoE Efficiency Study",
                "source_url": "https://arxiv.org/abs/2101.03961",
                "similarity": 0.88,
                "distance": 0.12,
            }
        ]

        raw_output = knowledge_retrieval.invoke({"query": "MoE efficiency", "top_k": 1})
        data = json.loads(raw_output)

        self.assertIn("documents", data)
        self.assertEqual(len(data["documents"]), 1)
        doc = data["documents"][0]
        self.assertEqual(doc["rank"], 1)
        self.assertIn("FLOPs", doc["text"])
        self.assertEqual(doc["title"], "MoE Efficiency Study")
        self.assertEqual(doc["url"], "https://arxiv.org/abs/2101.03961")
        self.assertAlmostEqual(doc["score"], 0.88)
        self.assertAlmostEqual(doc["distance"], 0.12)

    @patch("qubettera.agents.tools.retrieval_tool.retrieve")
    def test_failed_retrieval_returns_error_envelope(self, mock_retrieve) -> None:
        mock_retrieve.side_effect = ConnectionError("Kaggle Ollama service unreachable")

        raw_output = knowledge_retrieval.invoke({"query": "MoE efficiency", "top_k": 1})
        data = json.loads(raw_output)

        self.assertEqual(data["documents"], [])
        self.assertIn("error", data)
        self.assertIn("ConnectionError", data["error"])


class TestSearchTool(unittest.TestCase):
    def test_tool_metadata(self) -> None:
        self.assertEqual(live_web_search.name, "live_web_search")
        self.assertIn("live search", live_web_search.description)

    @patch("qubettera.agents.tools.search_tool.get_provider")
    def test_successful_search_returns_markdown(self, mock_get_provider) -> None:
        mock_provider = MagicMock()
        mock_provider.search.return_value = [
            SearchResult(
                title="DeepSeek-V3 Technical Report",
                url="https://arxiv.org/abs/2412.19437",
                content="DeepSeek-V3 adopts Multi-head Latent Attention and DeepSeekMoE.",
                snippet="DeepSeek-V3 adopts Multi-head Latent Attention...",
            )
        ]
        mock_get_provider.return_value = mock_provider

        output = live_web_search.invoke({"query": "DeepSeek-V3"})
        self.assertIn("DeepSeek-V3 Technical Report", output)
        self.assertIn("https://arxiv.org/abs/2412.19437", output)

    @patch("qubettera.agents.tools.search_tool.get_provider")
    def test_empty_search_returns_not_found(self, mock_get_provider) -> None:
        mock_provider = MagicMock()
        mock_provider.search.return_value = []
        mock_get_provider.return_value = mock_provider

        output = live_web_search.invoke({"query": "unknown-nonexistent-query-xyz"})
        self.assertIn("No results found", output)

    @patch("qubettera.agents.tools.search_tool.get_provider")
    def test_provider_error_is_caught(self, mock_get_provider) -> None:
        mock_provider = MagicMock()
        mock_provider.search.side_effect = RuntimeError("Rate limit exceeded")
        mock_get_provider.return_value = mock_provider

        output = live_web_search.invoke({"query": "test"})
        self.assertIn("Error performing live search", output)


class TestCrawlTool(unittest.TestCase):
    def test_tool_metadata(self) -> None:
        self.assertEqual(deep_web_crawl.name, "deep_web_crawl")
        self.assertIn("Crawls a specific URL", deep_web_crawl.description)

    @patch("qubettera.agents.tools.crawl_tool.Crawl4AIProvider")
    def test_successful_crawl_returns_markdown(self, mock_provider_cls) -> None:
        mock_provider = MagicMock()
        mock_result = MagicMock()
        mock_result.title = "Sample Paper"
        mock_result.url = "https://example.com/paper"
        mock_result.content = "Full content of the paper."
        mock_provider.crawl_url.return_value = mock_result
        mock_provider_cls.return_value = mock_provider

        output = deep_web_crawl.invoke({"url": "https://example.com/paper"})
        self.assertIn("## Sample Paper", output)
        self.assertIn("https://example.com/paper", output)
        self.assertIn("Full content of the paper.", output)

    @patch("qubettera.agents.tools.crawl_tool.Crawl4AIProvider")
    def test_crawl_truncates_long_content(self, mock_provider_cls) -> None:
        mock_provider = MagicMock()
        mock_result = MagicMock()
        mock_result.title = "Long Document"
        mock_result.url = "https://example.com/long"
        mock_result.content = "A" * 10000
        mock_provider.crawl_url.return_value = mock_result
        mock_provider_cls.return_value = mock_provider

        output = deep_web_crawl.invoke({"url": "https://example.com/long"})
        self.assertIn("... (content truncated due to length)", output)
        self.assertLess(len(output), 9000)

    @patch("qubettera.agents.tools.crawl_tool.Crawl4AIProvider")
    def test_crawl_failure_returns_error_message(self, mock_provider_cls) -> None:
        mock_provider = MagicMock()
        mock_provider.crawl_url.side_effect = Exception("Page timeout")
        mock_provider_cls.return_value = mock_provider

        output = deep_web_crawl.invoke({"url": "https://example.com/bad"})
        self.assertIn("Error crawling https://example.com/bad", output)


if __name__ == "__main__":
    unittest.main()
