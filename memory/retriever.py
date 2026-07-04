"""
memory/retriever.py

Hybrid FTS5 keyword + vector search over memory_chunks (Phase 9). This is
the retrieval substitute for a genuine million-token context window --
see docs/upgrade-guide/14-phase-9-retrieval-memory.md for the hardware
math on why that isn't achievable on a 24GB Mac. retrieve_context() is the
single entry point run.py calls; everything else here is an
implementation detail it composes.
"""

import sqlite3
import struct

from memory.embeddings import embed
from orchestrator.config_loader import get_memory_config
from orchestrator.database import get_all_memory_chunks, keyword_search_memory_chunks


def _unpack_embedding(blob: bytes) -> list[float]:
    count = len(blob) // 4
    return list(struct.unpack(f"{count}f", blob))


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _try_sqlite_vec_similarity(
    query_vector: list[float], chunks: list[dict]
) -> list[dict] | None:
    """
    Attempt to compute cosine similarity for `chunks` against
    `query_vector` using the sqlite-vec extension's vec_distance_cosine()
    scalar function on a scratch in-memory connection (this never touches
    the real database -- it's only used as a computation engine here).

    Returns None -- never raises -- if the `sqlite_vec` package isn't
    installed, the extension fails to load, or the query fails for any
    other reason, signaling the caller to use the pure-Python brute-force
    path in vector_search() instead. That fallback is a deliberate,
    documented design choice at this project's scale (see chunking/
    retriever module docstrings), not a lesser-quality shortcut.
    """
    try:
        import sqlite_vec

        conn = sqlite3.connect(":memory:")
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)

        query_blob = struct.pack(f"{len(query_vector)}f", *query_vector)
        scored = []
        for chunk in chunks:
            if not chunk.get("embedding"):
                continue
            row = conn.execute(
                "SELECT vec_distance_cosine(?, ?) AS distance",
                (chunk["embedding"], query_blob),
            ).fetchone()
            distance = row[0]
            scored.append({
                "id": chunk["id"],
                "source_type": chunk["source_type"],
                "source_ref": chunk["source_ref"],
                "chunk_text": chunk["chunk_text"],
                "score": 1.0 - distance,
            })
        conn.close()
        return scored
    except Exception:
        return None


def keyword_search(query: str, k: int) -> list[dict]:
    """BM25-ranked keyword search via the memory_chunks_fts virtual table."""
    return keyword_search_memory_chunks(query, k)


def vector_search(query: str, k: int, embed_fn=embed) -> list[dict]:
    """
    Rank stored chunks by cosine similarity to the embedded query. Tries
    the sqlite-vec extension first; if it isn't available or the query
    fails for any reason, falls back to a pure-Python brute-force scan
    over every stored embedding -- fast enough at this project's actual
    scale (thousands, not millions, of chunks).

    `embed_fn` is injectable so tests can supply a deterministic fake
    embedding function instead of calling the real nomic-embed-text model.
    """
    query_vector = embed_fn(query)
    chunks = get_all_memory_chunks()

    scored = _try_sqlite_vec_similarity(query_vector, chunks)

    if scored is None:
        scored = []
        for chunk in chunks:
            if not chunk.get("embedding"):
                continue
            chunk_vector = _unpack_embedding(chunk["embedding"])
            similarity = _cosine_similarity(query_vector, chunk_vector)
            scored.append({
                "id": chunk["id"],
                "source_type": chunk["source_type"],
                "source_ref": chunk["source_ref"],
                "chunk_text": chunk["chunk_text"],
                "score": similarity,
            })

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:k]


def hybrid_search(query: str, k: int, embed_fn=embed) -> list[dict]:
    """
    Combine keyword_search and vector_search results via a simple
    normalized weighted sum -- not full reciprocal rank fusion, since
    over-engineering the re-ranking isn't worth it at this project's
    scale. Both signals are normalized to [0, 1] before combining so
    neither dominates purely because of its native scale (bm25() scores
    are unbounded and more-negative-is-better; cosine similarity is
    already in [-1, 1] but on a very different scale).
    """
    keyword_results = keyword_search(query, k * 2)
    vector_results = vector_search(query, k * 2, embed_fn=embed_fn)

    combined: dict[int, dict] = {}

    if keyword_results:
        flipped = [-r["rank"] for r in keyword_results]
        max_flipped = max(flipped) if max(flipped) > 0 else 1.0
        for result, flipped_rank in zip(keyword_results, flipped):
            normalized = flipped_rank / max_flipped
            combined[result["id"]] = {
                "id": result["id"], "source_type": result["source_type"],
                "source_ref": result["source_ref"], "chunk_text": result["chunk_text"],
                "keyword_score": normalized, "vector_score": 0.0,
            }

    if vector_results:
        max_score = max((r["score"] for r in vector_results), default=0.0)
        max_score = max_score if max_score > 0 else 1.0
        for result in vector_results:
            normalized = result["score"] / max_score
            if result["id"] in combined:
                combined[result["id"]]["vector_score"] = normalized
            else:
                combined[result["id"]] = {
                    "id": result["id"], "source_type": result["source_type"],
                    "source_ref": result["source_ref"], "chunk_text": result["chunk_text"],
                    "keyword_score": 0.0, "vector_score": normalized,
                }

    merged = list(combined.values())
    for item in merged:
        item["combined_score"] = 0.5 * item["keyword_score"] + 0.5 * item["vector_score"]
    merged.sort(key=lambda item: item["combined_score"], reverse=True)

    return merged[:k]


def retrieve_context(goal: str, k: int | None = None, embed_fn=embed) -> str:
    """
    The single entry point run.py calls: runs hybrid_search over `goal`
    and formats the top chunks into a clearly-labeled context block ready
    to prepend to a prompt. Always capped at the configured (or given)
    top_k -- never "just add everything that matched," since that would
    reintroduce the unbounded-context problem this phase exists to avoid.
    Returns an empty string if nothing is indexed yet.
    """
    top_k = k if k is not None else get_memory_config().get("top_k", 5)
    results = hybrid_search(goal, top_k, embed_fn=embed_fn)
    if not results:
        return ""

    lines = ["RELEVANT CONTEXT FROM PRIOR RUNS:"]
    for result in results:
        lines.append(f"- ({result['source_type']} {result['source_ref']}): {result['chunk_text']}")
    return "\n".join(lines)
