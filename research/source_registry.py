"""
research/source_registry.py

Tracks every source fetched during one research run, persisted as a
single JSON file alongside that run's other artifacts under
runs/<timestamp>/ -- this doesn't need its own database table unless
cross-run source lookups become useful later.
"""

import hashlib
import json
from pathlib import Path


def hash_content(text: str) -> str:
    """A stable content hash for change detection -- not a security
    control, just a cheap way to notice if a source's text changed
    between runs."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class SourceRegistry:
    """
    Tracks fetched sources for one research run. `register()` takes the
    guide's specified (url, title, fetched_at, content_hash) plus an
    additional `text` field: research/citation_verifier.py's
    verify_citation() needs the source's actual fetched text to check
    claim support, not just its hash, so the registry stores both.
    """

    def __init__(self):
        self._sources: dict[str, dict] = {}
        self._next_id = 1

    def register(
        self, url: str, title: str, fetched_at: str, content_hash: str, text: str = "",
    ) -> str:
        """
        Register a fetched source and return a stable source_id (e.g.
        "S1"). Registering the same URL twice returns the existing
        source_id rather than creating a duplicate entry.
        """
        for source_id, source in self._sources.items():
            if source["url"] == url:
                return source_id

        source_id = f"S{self._next_id}"
        self._next_id += 1
        self._sources[source_id] = {
            "source_id": source_id,
            "url": url,
            "title": title,
            "fetched_at": fetched_at,
            "content_hash": content_hash,
            "text": text,
        }
        return source_id

    def get_source(self, source_id: str) -> dict | None:
        return self._sources.get(source_id)

    def all_sources(self) -> dict[str, dict]:
        return dict(self._sources)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self._sources, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "SourceRegistry":
        registry = cls()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        registry._sources = data
        if data:
            registry._next_id = max(int(source_id[1:]) for source_id in data) + 1
        return registry
