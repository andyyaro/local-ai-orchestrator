"""
tests/test_fetcher.py

Phase 10: robots.txt-respecting fetch. Every test here mocks
urllib.robotparser and requests -- zero real network calls, matching the
same discipline Phase 7's tests use for MockCloudAdapter.
"""

from unittest.mock import MagicMock

import pytest
import requests

from research.fetcher import FetchError, RobotsDisallowedError, fetch_url


def _mock_robots(monkeypatch, allowed: bool):
    mock_parser = MagicMock()
    mock_parser.read.return_value = None
    mock_parser.can_fetch.return_value = allowed
    monkeypatch.setattr(
        "research.fetcher.urllib.robotparser.RobotFileParser", lambda: mock_parser,
    )


def test_fetch_url_refuses_when_robots_txt_disallows(monkeypatch):
    _mock_robots(monkeypatch, allowed=False)

    # requests.get must never even be attempted once robots.txt disallows.
    def _fail_if_called(*args, **kwargs):
        raise AssertionError("requests.get must not be called when robots.txt disallows")

    monkeypatch.setattr("research.fetcher.requests.get", _fail_if_called)

    with pytest.raises(RobotsDisallowedError):
        fetch_url("https://example.com/disallowed-page")


def test_fetch_url_fails_closed_when_robots_txt_cannot_be_read(monkeypatch):
    """If robots.txt itself can't be fetched/parsed, treat the URL as
    disallowed rather than assuming permission."""
    mock_parser = MagicMock()
    mock_parser.read.side_effect = Exception("connection refused")
    monkeypatch.setattr(
        "research.fetcher.urllib.robotparser.RobotFileParser", lambda: mock_parser,
    )

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("requests.get must not be called when robots.txt can't be read")

    monkeypatch.setattr("research.fetcher.requests.get", _fail_if_called)

    with pytest.raises(RobotsDisallowedError):
        fetch_url("https://example.com/some-page")


def test_fetch_url_converts_html_to_plain_text_when_allowed(monkeypatch):
    _mock_robots(monkeypatch, allowed=True)

    html = b"<html><head><style>.x{}</style></head><body><script>evil()</script><p>Hello world.</p></body></html>"
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.iter_content.return_value = [html]
    monkeypatch.setattr("research.fetcher.requests.get", lambda *a, **kw: mock_response)

    page = fetch_url("https://example.com/page")

    assert "Hello world." in page.text
    assert "evil()" not in page.text
    assert page.url == "https://example.com/page"


def test_fetch_url_raises_fetch_error_on_oversized_response(monkeypatch):
    _mock_robots(monkeypatch, allowed=True)

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.iter_content.return_value = [b"x" * 1000 for _ in range(10)]
    monkeypatch.setattr("research.fetcher.requests.get", lambda *a, **kw: mock_response)
    monkeypatch.setattr(
        "research.fetcher.get_research_config",
        lambda: {"max_fetch_bytes": 500, "respect_robots_txt": True,
                  "user_agent": "TestBot/0.1", "fetch_timeout_seconds": 15},
    )

    with pytest.raises(FetchError):
        fetch_url("https://example.com/huge-page")


def test_fetch_url_raises_fetch_error_on_connection_failure(monkeypatch):
    _mock_robots(monkeypatch, allowed=True)

    def _raise_connection_error(*args, **kwargs):
        raise requests.exceptions.ConnectionError("refused")

    monkeypatch.setattr("research.fetcher.requests.get", _raise_connection_error)

    with pytest.raises(FetchError):
        fetch_url("https://example.com/unreachable")
