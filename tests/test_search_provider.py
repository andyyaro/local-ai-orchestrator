"""
tests/test_search_provider.py

Phase 10: search abstraction. MockSearchProvider is what every test
(including all of this file) uses -- zero real network calls.
"""

import pytest

from research.search_provider import (
    BraveSearchProvider,
    MockSearchProvider,
    SearchResult,
    get_search_provider,
)


def test_mock_search_provider_returns_canned_results():
    provider = MockSearchProvider()
    results = provider.search("anything", k=5)
    assert results
    assert all(isinstance(r, SearchResult) for r in results)


def test_mock_search_provider_respects_k():
    provider = MockSearchProvider(
        canned_results=[SearchResult(title=f"T{i}", url=f"https://x.com/{i}", snippet="s") for i in range(5)]
    )
    assert len(provider.search("q", k=2)) == 2


def test_get_search_provider_returns_mock_by_default():
    provider = get_search_provider("mock")
    assert isinstance(provider, MockSearchProvider)


def test_get_search_provider_unknown_name_raises():
    with pytest.raises(ValueError):
        get_search_provider("nonexistent-provider")


def test_brave_search_provider_never_makes_a_real_call_and_raises_not_implemented():
    """Deliberately deferred (see BraveSearchProvider's docstring) --
    confirms it fails loudly rather than silently attempting a real,
    unverified API call."""
    provider = BraveSearchProvider()
    with pytest.raises(NotImplementedError):
        provider.search("query", k=5)
