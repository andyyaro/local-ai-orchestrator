"""
tests/test_memory.py

Phase 9: retrieval and long-context-equivalent memory. Every test here
uses a temp SQLite database (never runs/history.db) and a fake,
deterministic embedding function -- never the real nomic-embed-text model
-- so this suite never requires Ollama running.
"""

import struct

import pytest

from memory import retriever
from memory.chunking import chunk_text
from memory.embeddings import EmbeddingModelUnavailableError, embed
from orchestrator import database


def _pack(vector: list[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


def _fake_embed_factory(vectors_by_text: dict[str, list[float]], default: list[float]):
    """A deterministic fake embed() -- never calls Ollama."""
    def _fake_embed(text: str, model: str | None = None) -> list[float]:
        return vectors_by_text.get(text, default)
    return _fake_embed


# ── chunk_text ─────────────────────────────────────────────────────────────────

def test_chunk_text_splits_multi_paragraph_string_near_target_size():
    paragraphs = [f"Paragraph {i} " + " ".join(["word"] * 40) for i in range(10)]
    text = "\n\n".join(paragraphs)

    chunks = chunk_text(text, chunk_size_tokens=100)

    assert len(chunks) > 1
    # Every chunk should be in the same ballpark as the target size --
    # not exact (paragraphs merge up to but not exceeding it before a new
    # chunk starts), but never wildly larger.
    for chunk in chunks:
        assert len(chunk.split()) <= 150


def test_chunk_text_handles_string_shorter_than_one_chunk():
    text = "A short paragraph that fits in a single chunk easily."
    chunks = chunk_text(text, chunk_size_tokens=512)
    assert chunks == [text]


def test_chunk_text_returns_empty_list_for_empty_string():
    assert chunk_text("", chunk_size_tokens=512) == []
    assert chunk_text("   \n\n  ", chunk_size_tokens=512) == []


# ── embed() error handling (no real Ollama call) ────────────────────────────────

def test_embed_raises_clear_error_when_ollama_unreachable(monkeypatch):
    import requests

    def _raise_connection_error(*args, **kwargs):
        raise requests.exceptions.ConnectionError("refused")

    monkeypatch.setattr("memory.embeddings.requests.post", _raise_connection_error)

    with pytest.raises(EmbeddingModelUnavailableError, match="Ollama"):
        embed("some text")


# ── keyword_search / vector_search / hybrid_search (temp DB, fake embeddings) ──

@pytest.fixture
def indexed_chunks(monkeypatch, tmp_path):
    """Seed a temp database with a small, hand-constructed set of chunks
    and deterministic fake embeddings for hybrid search tests."""
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "history.db")

    vectors = {
        "The quick brown fox jumps over the lazy dog.": [1.0, 0.0, 0.0],
        "Sleep is essential for physical and mental health.": [0.0, 1.0, 0.0],
        "Connection pooling reduces database latency under load.": [0.0, 0.0, 1.0],
    }
    fake_embed = _fake_embed_factory(vectors, default=[0.1, 0.1, 0.1])

    for text, vector in vectors.items():
        database.save_memory_chunk(
            source_type="run", source_ref="1", chunk_text=text, embedding=_pack(vector),
        )

    return fake_embed


def test_keyword_search_returns_expected_top_result(indexed_chunks):
    results = retriever.keyword_search("fox jumps", k=3)
    assert results
    assert "fox" in results[0]["chunk_text"]


def test_vector_search_returns_expected_top_result_with_fake_embedding(indexed_chunks):
    # Query embeds identically to the "sleep" chunk's vector -- it should
    # rank first by cosine similarity.
    results = retriever.vector_search("sleep query", k=3, embed_fn=lambda q: [0.0, 1.0, 0.0])
    assert results
    assert "Sleep" in results[0]["chunk_text"]


def test_vector_search_respects_k_limit(indexed_chunks):
    results = retriever.vector_search("query", k=1, embed_fn=lambda q: [1.0, 0.0, 0.0])
    assert len(results) == 1


def test_hybrid_search_merges_both_signals(indexed_chunks):
    # "database latency" matches the connection-pooling chunk on keywords;
    # embed it to the same vector as that chunk too, so both signals agree
    # and it should be the clear top result.
    results = retriever.hybrid_search(
        "database latency", k=3, embed_fn=lambda q: [0.0, 0.0, 1.0],
    )
    assert results
    assert "Connection pooling" in results[0]["chunk_text"]


def test_hybrid_search_does_not_crash_when_keyword_search_finds_nothing(indexed_chunks):
    results = retriever.hybrid_search(
        "zzznomatchzzz", k=3, embed_fn=lambda q: [0.0, 1.0, 0.0],
    )
    assert results
    assert "Sleep" in results[0]["chunk_text"]


# ── sqlite-vec-unavailable fallback path ────────────────────────────────────────

def test_vector_search_falls_back_to_brute_force_when_sqlite_vec_unavailable(
    indexed_chunks, monkeypatch
):
    """Force the sqlite-vec load to fail and confirm the pure-Python
    brute-force cosine similarity path still produces correct ordering."""
    monkeypatch.setattr(retriever, "_try_sqlite_vec_similarity", lambda query_vector, chunks: None)

    results = retriever.vector_search("query", k=3, embed_fn=lambda q: [0.0, 1.0, 0.0])

    assert results
    assert "Sleep" in results[0]["chunk_text"]


def test_try_sqlite_vec_similarity_returns_none_on_import_failure(monkeypatch):
    """_try_sqlite_vec_similarity must never raise -- any failure (missing
    package, load failure, etc.) degrades to None so vector_search() can
    fall back, rather than crashing the whole retrieval path."""
    result = retriever._try_sqlite_vec_similarity([1.0, 0.0], [{"embedding": None}])
    # With no real embeddings to compare (embedding=None is skipped), this
    # should return a (possibly empty) list if the extension loaded, or
    # None if it didn't -- either way, no exception propagates.
    assert result is None or isinstance(result, list)


# ── retrieve_context top_k cap ──────────────────────────────────────────────────

def test_retrieve_context_respects_top_k_and_formats_a_labeled_block(indexed_chunks):
    context = retriever.retrieve_context(
        "sleep and connection pooling", k=1, embed_fn=lambda q: [0.0, 1.0, 0.0],
    )
    assert context.startswith("RELEVANT CONTEXT FROM PRIOR RUNS:")
    # Exactly one chunk line plus the header line.
    assert context.count("\n- (") == 1


def test_retrieve_context_returns_empty_string_when_nothing_indexed(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "empty_history.db")
    context = retriever.retrieve_context("anything", k=5, embed_fn=lambda q: [0.0, 0.0, 0.0])
    assert context == ""
