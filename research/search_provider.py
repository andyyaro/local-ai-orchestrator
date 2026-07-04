"""
research/search_provider.py

Search abstraction for Phase 10 deep research. MockSearchProvider is what
every test uses and is also the config default
(research.search_provider: "mock") -- no real network call happens even
if research.internet_enabled and --enable-research are both set, unless
a real provider is explicitly configured.
"""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


class SearchProvider(ABC):
    """Every search provider must implement search(). No provider here
    is ever called unless research.internet_enabled and
    --enable-research both hold -- see research/run_research.py."""

    @abstractmethod
    def search(self, query: str, k: int) -> list[SearchResult]:
        """Return up to k search results for `query`."""


class MockSearchProvider(SearchProvider):
    """
    Deterministic, canned search results with no network call at all.
    This is what every test uses, and what research.search_provider:
    "mock" (the config default) selects.
    """

    def __init__(self, canned_results: list[SearchResult] | None = None):
        self.canned_results = canned_results or [
            SearchResult(
                title="Example Source One",
                url="https://example.com/source-one",
                snippet="A canned snippet used for deterministic testing.",
            ),
            SearchResult(
                title="Example Source Two",
                url="https://example.com/source-two",
                snippet="A second canned snippet used for deterministic testing.",
            ),
        ]

    def search(self, query: str, k: int) -> list[SearchResult]:
        return self.canned_results[:k]


class BraveSearchProvider(SearchProvider):
    """
    Real web search via the Brave Search API. Requires BRAVE_API_KEY in
    .env, read only via os.environ -- never hardcoded, never logged.

    Deliberately left unverified in this session, following this
    project's own precedent (see orchestrator/adapters.py's
    AnthropicAdapter from Phase 7): the current Brave Search API
    request/response schema has not been checked against Brave's official
    published documentation, so shipping a real call here risks targeting
    a stale endpoint or response shape. search() raises
    NotImplementedError until that verification happens; use
    MockSearchProvider for all development and testing in the meantime.
    """

    def __init__(self):
        self.api_key = os.environ.get("BRAVE_API_KEY")

    def search(self, query: str, k: int) -> list[SearchResult]:
        raise NotImplementedError(
            "BraveSearchProvider is not yet implemented: the Brave Search "
            "API request/response schema has not been verified against "
            "Brave's current published documentation in this session. "
            "Set research.search_provider: \"mock\" in config/models.yaml "
            "to use MockSearchProvider."
        )


def get_search_provider(provider_name: str) -> SearchProvider:
    """Return the configured search provider by name. Valid options:
    "mock" (default, no network) and "brave" (unverified stub, see
    BraveSearchProvider)."""
    if provider_name == "mock":
        return MockSearchProvider()
    if provider_name == "brave":
        return BraveSearchProvider()
    raise ValueError(
        f"Unknown search provider '{provider_name}'. Valid options: mock, brave"
    )
