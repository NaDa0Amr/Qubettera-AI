from abc import ABC, abstractmethod
from typing import List, Dict, Any

class SearchResult:
    """Normalized search result."""
    def __init__(self, title: str, url: str, content: str, snippet: str = ""):
        self.title = title
        self.url = url
        self.content = content   # Full text or detailed content
        self.snippet = snippet   # Short excerpt for citation

    def to_markdown(self, index: int) -> str:
        """Format as Markdown with citation."""
        return f"[{index}] **{self.title}**\n    URL: {self.url}\n    {self.content or self.snippet}\n"


class SearchProvider(ABC):
    """Abstract base class for search providers."""

    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """
        Perform a live search and return normalized results.
        Each result must have title, url, and content.
        """
        pass