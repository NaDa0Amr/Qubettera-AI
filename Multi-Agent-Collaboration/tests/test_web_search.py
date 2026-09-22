from __future__ import annotations

import unittest

from src.web_search import WebSearchExecutionError, search_web


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self.payload


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[dict] = []

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return self.response


class WebSearchTests(unittest.TestCase):
    def test_returns_structured_web_results_in_keyless_mode(self) -> None:
        session = FakeSession(
            FakeResponse(
                {
                    "results": [
                        {
                            "title": "Recent MoE Research",
                            "url": "https://example.org/research",
                            "content": "A current summary of mixture-of-experts research.",
                            "score": 0.91,
                        }
                    ]
                }
            )
        )

        results = search_web(
            "latest MoE research",
            max_results=3,
            api_key="",
            session=session,
        )

        self.assertEqual(results[0]["tool"], "search_web")
        self.assertEqual(results[0]["url"], "https://example.org/research")
        self.assertEqual(results[0]["score"], 0.91)
        call = session.calls[0]
        self.assertEqual(call["headers"]["X-Tavily-Access-Mode"], "keyless")
        self.assertNotIn("Authorization", call["headers"])
        self.assertEqual(call["json"]["max_results"], 3)

    def test_uses_bearer_header_when_api_key_is_present(self) -> None:
        session = FakeSession(FakeResponse({"results": []}))
        search_web("test query", api_key="tvly-test", session=session)
        headers = session.calls[0]["headers"]
        self.assertEqual(headers["Authorization"], "Bearer tvly-test")
        self.assertNotIn("X-Tavily-Access-Mode", headers)

    def test_rate_limit_error_is_controlled(self) -> None:
        session = FakeSession(FakeResponse({}, status_code=429))
        with self.assertRaisesRegex(WebSearchExecutionError, "limit was reached"):
            search_web("test query", api_key="", session=session)

    def test_rejects_invalid_max_results(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 1 and 10"):
            search_web(
                "test query",
                max_results=11,
                api_key="",
                session=FakeSession(FakeResponse({"results": []})),
            )


if __name__ == "__main__":
    unittest.main()
