"""Tool for deep web crawling and content extraction.

Uses Crawl4AI to extract clean Markdown content from a given URL.
"""

from __future__ import annotations

import logging

from langchain_core.tools import tool

from ..search.crawl4ai import Crawl4AIProvider

logger = logging.getLogger(__name__)

@tool
def deep_web_crawl(url: str) -> str:
    """
    Crawls a specific URL and extracts clean, LLM-ready Markdown content.
    
    Use this tool when:
    - You have a specific URL and need to extract detailed information from it.
    - The live_web_search tool only returned a snippet, but you need the full article.
    - You want to extract content from a known source (e.g., arXiv paper, blog post, documentation).
    
    Args:
        url: The full URL to crawl (e.g., "https://arxiv.org/abs/2401.12345")
    
    Returns:
        Clean Markdown content from the page, or an error message if crawling fails.
    """
    try:
        # Instantiate the Crawl4AI provider
        provider = Crawl4AIProvider()
        
        # Crawl the URL
        result = provider.crawl_url(url)
        
        # Format the output
        if result.content and "Error" not in result.content:
            # Truncate if too long (context window protection)
            content = result.content
            if len(content) > 8000:
                content = content[:8000] + "\n\n... (content truncated due to length)"
            
            return f"""## {result.title}

**URL:** {result.url}

{content}
"""
        else:
            return f"Failed to extract content from {url}: {result.content or 'Unknown error'}"
            
    except Exception as e:
        logger.error(f"Crawl tool error: {e}")
        return f"Error crawling {url}: {str(e)}"