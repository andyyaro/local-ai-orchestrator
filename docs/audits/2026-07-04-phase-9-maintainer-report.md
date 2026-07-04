# Phase 9 Maintainer Report — Retrieval and Long-Context-Equivalent Memory

## Goal

Give the pipeline access to relevant context from prior runs and project
files through retrieval — local embeddings plus hybrid keyword/vector
search — instead of pretending the system can hold a huge context window.

## What was built

1. **`config/models.yaml`** — merged new retrieval keys into the
   **existing** `memory:` block (`retrieval_enabled: false`,
   `embedding_model: "nomic-embed-text"`, `top_k: 5`,
   `chunk_size_tokens: 512`) rather than adding a second top-level
   `memory:` key. A duplicate top-level YAML key would have silently
   shadowed the existing `memory.keep_alive` setting under PyYAML's
   default duplicate-key handling (last one wins) — caught this during
   inspection before writing any config, not after.
2. **`orchestrator/config_loader.py`** — `get_memory_config()` added,
   following the existing `get_resilience_config()`/`get_cloud_config()`
   pattern.
3. **`requirements.txt`** — added `sqlite-vec>=0.1.0`.
4. **`orchestrator/database.py`** — added `memory_chunks` table plus an
   FTS5 virtual table (`memory_chunks_fts`) exactly as specified, **with
   the three sync triggers FTS5's external-content-table pattern
   requires** (`memory_chunks_ai`/`_ad`/`_au` — insert/delete/update).
   Without these triggers, `memory_chunks_fts` would never see any data
   inserted into `memory_chunks`, and keyword search would always return
   empty — confirmed this works with a real insert-then-search smoke test
   before writing the rest of the phase. Added `save_memory_chunk()`,
   `get_all_memory_chunks()`, and `keyword_search_memory_chunks()`
   (BM25-ranked, degrades to an empty list rather than raising on an FTS5
   MATCH syntax error).
5. **`memory/` package** (new):
   - `chunking.py` — `chunk_text()`, paragraph-boundary chunking with
     word-count as the token approximation, documented as such.
   - `embeddings.py` — `embed()` calling Ollama's `/api/embeddings`
     endpoint directly (not through `ModelAdapter`, since it returns a
     vector, not text). Raises `EmbeddingModelUnavailableError` naming
     the exact `ollama pull nomic-embed-text` command on any connection,
     timeout, HTTP error, or empty-response case — never a silent empty
     vector, never an auto-pull.
   - `retriever.py` — `keyword_search()`, `vector_search()`,
     `hybrid_search()` (normalized weighted sum, not full reciprocal rank
     fusion, per the guide's explicit "don't over-engineer" note), and
     `retrieve_context()` as the single pipeline entry point, strictly
     capped at `top_k`.
   - `indexer.py` — `index_run()`, `index_project_file()`, and
     `summarize_run()` (the one function that calls a real local model,
     using whatever light role model the active profile assigns to
     `planner` — the guide's "cheap, like the fast profile's role model"
     characterization, applied via the actually-active profile rather
     than hardcoding profile selection).
6. **`run.py`** — retrieval wired in right after path classification,
   gated by `memory.retrieval_enabled` (default `false`). If enabled,
   `retrieve_context(refined_goal)` is called once; its output is
   prepended to an `augmented_goal` string used **only** for the Planner
   and Builder calls (per the guide's exact instruction), leaving
   Critic/Fixer/Judge/Synthesizer on the unmodified `refined_goal`/`goal`.
   `EmbeddingModelUnavailableError` is caught and printed as a skip
   notice rather than crashing the pipeline — retrieval is an opt-in
   enhancement, not a hard requirement to produce output.
7. **`orchestrator/graph.py`** — mirrored the same wiring: `node_supervisor`
   computes `augmented_goal` once (added to `PipelineState` in
   `orchestrator/state.py`) and stores it in state; `node_planner`/
   `node_builder` read `state.get("augmented_goal") or state["refined_goal"]`.

## The sqlite-vec fallback design — verified, not just assumed

Rather than write SQL against sqlite-vec's virtual-table KNN syntax
(which has evolved across versions and could not be verified against
current docs without live access in this session), `vector_search()`
uses the extension's `vec_distance_cosine()` **scalar function** — a
smaller, more stable piece of API surface — wrapped in
`_try_sqlite_vec_similarity()`, which returns `None` (never raises) on
any failure: missing package, extension load failure, or an unexpected
SQL error. `vector_search()` falls back to a pure-Python brute-force
cosine similarity scan whenever that happens.

**This was verified for real, not left as an untested assumption**:
`pip install sqlite-vec` was run in this session (a normal Python package
install, not a model download or paid call), and the extension **loaded
and worked correctly** — a direct test against `_try_sqlite_vec_similarity()`
with hand-computed vectors (`[0,1,0]` query against `[1,0,0]` and `[0,1,0]`
stored embeddings) returned scores of `0.0` and `1.0` exactly as expected.
The full `tests/test_memory.py` suite was then re-run with the extension
installed and **still passed** — confirming the accelerated path and the
brute-force fallback both produce correct, consistent results. The
fallback path itself is separately exercised by
`test_vector_search_falls_back_to_brute_force_when_sqlite_vec_unavailable`,
which forces `_try_sqlite_vec_similarity` to return `None` regardless of
whether the extension is actually installed.

## Tests added

`tests/test_memory.py` (13 tests), all using a temp SQLite database
(`monkeypatch.setattr(database, "DB_PATH", tmp_path / ...)`) and
deterministic fake embedding functions — never the real
`nomic-embed-text` model, never Ollama:

- `chunk_text`: multi-paragraph splitting near target size, a
  shorter-than-one-chunk string, and empty/whitespace-only input.
- `embed()`: raises `EmbeddingModelUnavailableError` on a connection
  failure (mocked `requests.post`), never calling real Ollama.
- `keyword_search`/`vector_search`/`hybrid_search`: expected top result
  for a small, hand-constructed indexed set; `vector_search` respects
  `k`; `hybrid_search` merges both signals and degrades gracefully when
  keyword search finds nothing.
- The sqlite-vec-unavailable fallback path, forced via monkeypatching
  `_try_sqlite_vec_similarity` to return `None`, still produces correct
  similarity ordering.
- `retrieve_context`: respects `top_k`, formats the labeled context
  block correctly, and returns an empty string when nothing is indexed.

## Tests run

```
ruff check .                    → All checks passed!
pytest tests/test_memory.py -v  → 13 passed
pytest tests/ -v                → 160 passed
```

## sqlite-vec status in this environment

**Loaded and worked successfully.** `pip install sqlite-vec` installed
version `0.1.9`; the extension loads via `sqlite_vec.load(conn)` and
`vec_distance_cosine()` executes correctly against packed-float BLOB
embeddings, verified with a direct hand-computed test (see above) and by
re-running the full memory test suite with it installed. The brute-force
fallback path was also independently verified via the forced-failure
test — both paths are exercised and correct, not just one assumed to work.

## Files changed

- `config/models.yaml`
- `orchestrator/config_loader.py`
- `orchestrator/database.py`
- `orchestrator/graph.py`
- `orchestrator/state.py`
- `requirements.txt`
- `run.py`
- `memory/__init__.py` (new)
- `memory/chunking.py` (new)
- `memory/embeddings.py` (new)
- `memory/indexer.py` (new)
- `memory/retriever.py` (new)
- `tests/test_memory.py` (new)
- `docs/audits/2026-07-04-phase-9-maintainer-report.md` (new)

## Remaining risks / TODOs

- `memory.retrieval_enabled` remains `false` in the shipped config, as
  required. No real embedding calls or indexing happened against real
  project data in this session — `nomic-embed-text` is not pulled
  locally (confirmed via `ollama list` in an earlier phase), and this
  phase never pulls a model automatically.
- `indexer.py`'s `index_run()`/`index_project_file()` are not yet called
  from anywhere automatically (e.g., auto-indexing every completed run).
  Wiring that in was not part of this phase's explicit scope (the guide's
  step 9 only asks to wire `retrieve_context()` into the prompt path) —
  a follow-up could call `index_run(db_run_id)` at the end of
  `run_pipeline()` once a user has retrieval enabled and wants their own
  history to actually become searchable.
- `hybrid_search`'s weighting (0.5/0.5 normalized weighted sum) is a
  simple, documented starting point per the guide's explicit "don't
  over-engineer" instruction — real-world tuning (once someone has actual
  indexed history to search) may suggest different weights.

## Commit

```
feat: add local embedding-based retrieval memory, off by default
```
