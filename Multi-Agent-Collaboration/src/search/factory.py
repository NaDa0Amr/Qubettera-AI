import os
from .base import SearchProvider
from .duckduckgo import DuckDuckGoProvider
from .tavily import TavilyProvider

def get_search_provider(provider: str = None) -> SearchProvider:
    """
    Factory for search providers.
    Provider can be set via environment variable SEARCH_PROVIDER.
    Options: 'duckduckgo', 'tavily'. Default: 'duckduckgo'.
    """
    provider = provider or os.getenv("SEARCH_PROVIDER", "duckduckgo")
    if provider == "duckduckgo":
        return DuckDuckGoProvider()
    elif provider == "tavily":
        return TavilyProvider()
    else:
        raise ValueError(f"Unsupported search provider: {provider}")