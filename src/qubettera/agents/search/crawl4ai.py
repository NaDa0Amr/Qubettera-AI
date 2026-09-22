import asyncio
import logging
from typing import List
from .base import SearchProvider, SearchResult

try:
    from crawl4ai import AsyncWebCrawler
except ImportError:
    AsyncWebCrawler = None
    logging.warning("crawl4ai not installed. Crawl4AI provider will not work.")

class Crawl4AIProvider(SearchProvider):
    """
    Crawl4AI provider – extracts content from a given URL.
    This is not a search engine; it's for deep extraction of a specific page.
    It can be used in addition to a search provider.
    """
    def __init__(self):
        if AsyncWebCrawler is None:
            raise ImportError("Please install crawl4ai: pip install crawl4ai")

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """
        Here, 'query' is treated as a URL to crawl.
        For a generic search, you would need to combine with a search API first.
        This provider is best used as a separate tool, not a direct replacement.
        """
        raise NotImplementedError("Crawl4AI is a crawler, not a search API. Use it with a specific URL.")
    
    def crawl_url(self, url: str) -> SearchResult:
        """Crawl a single URL and return content."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async def crawl():
                async with AsyncWebCrawler() as crawler:
                    result = await crawler.arun(url)
                    markdown = result.markdown if result else ""
                    return markdown
            markdown = loop.run_until_complete(crawl())
            # Truncate long content
            if len(markdown) > 5000:
                markdown = markdown[:5000] + "\n... (truncated)"
            return SearchResult(
                title=url,
                url=url,
                content=markdown,
                snippet=markdown[:200]
            )
        except Exception as e:
            logging.error(f"Crawl failed: {e}")
            return SearchResult(
                title=url,
                url=url,
                content=f"Error crawling: {str(e)}",
                snippet=""
            )
        finally:
            loop.close()