"""
research/fetcher.py

Robots.txt-respecting URL fetch for Phase 10 deep research. Fetched
content is always untrusted -- see research/prompt_injection_guard.py for
the sanitization/wrapping rule every fetched page must go through before
reaching a prompt.
"""

import urllib.robotparser
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from orchestrator.config_loader import get_research_config


@dataclass
class FetchedPage:
    url: str
    text: str
    fetched_at: str


class RobotsDisallowedError(Exception):
    """
    Raised when a URL's robots.txt disallows fetching it, or when
    robots.txt itself can't be fetched/parsed. This project treats
    respect_robots_txt as a hard rule, not a toggle to bypass -- see
    config/models.yaml's comment on that setting. Note this is the
    practical, automatable part of "respect robots.txt / terms where
    practical"; it is not a complete Terms-of-Service compliance
    guarantee, which can't be automated generically.
    """


class FetchError(Exception):
    """Raised for any other fetch failure: timeout, HTTP error, or an
    oversized response exceeding max_fetch_bytes."""


def _robots_txt_allows(url: str, user_agent: str) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)
    try:
        parser.read()
    except Exception:
        # If robots.txt itself can't be fetched or parsed, fail closed --
        # treat the URL as disallowed rather than assuming permission.
        return False
    return parser.can_fetch(user_agent, url)


def fetch_url(url: str) -> FetchedPage:
    """
    Fetch `url`, respecting robots.txt, a real identifying User-Agent
    (research.user_agent), fetch_timeout_seconds, and max_fetch_bytes.
    Converts HTML to plain text via BeautifulSoup (stripping <script> and
    <style> tags) rather than passing raw HTML into a prompt.

    Raises RobotsDisallowedError if robots.txt disallows fetching this
    URL (or can't be checked at all -- fail closed). Raises FetchError
    for any other failure: connection error, timeout, HTTP error status,
    or a response exceeding max_fetch_bytes.
    """
    config = get_research_config()
    user_agent = config.get("user_agent", "LocalAIOrchestratorResearchBot/0.1")
    timeout = config.get("fetch_timeout_seconds", 15)
    max_bytes = config.get("max_fetch_bytes", 2_000_000)

    if config.get("respect_robots_txt", True) and not _robots_txt_allows(url, user_agent):
        raise RobotsDisallowedError(f"robots.txt disallows fetching {url}")

    try:
        resp = requests.get(
            url, headers={"User-Agent": user_agent}, timeout=timeout, stream=True,
        )
        resp.raise_for_status()

        content = b""
        for chunk in resp.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > max_bytes:
                raise FetchError(f"{url} exceeded max_fetch_bytes ({max_bytes})")
    except requests.exceptions.RequestException as exc:
        raise FetchError(f"Failed to fetch {url}: {exc}") from exc

    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)

    return FetchedPage(
        url=url, text=text,
        fetched_at=datetime.now().isoformat(timespec="seconds"),
    )
