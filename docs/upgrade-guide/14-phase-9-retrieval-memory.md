# 14 — Phase 9: Retrieval and Long-Context-Equivalent Memory

## Goal

Give the pipeline access to relevant context from prior runs and project
files through retrieval — local embeddings plus hybrid keyword/vector
search — instead of pretending the system can hold a huge context window.

## Why it matters

Both research reports agree on this point with hard numbers: a genuine
1-million-token context window is not realistic on a 24GB Mac. The KV cache
for long-context attention scales with sequence length, and even at
aggressive 2-bit quantization, published research (KVQuant, NeurIPS 2024)
states that serving a 7B model at a 1M-token context requires **64GB just
for the KV cache** — on a single datacenter GPU, before you even count model
weights. Ollama's usable GPU memory on a 24GB Mac is roughly 16GB total,
already spoken for by whatever model is loaded. A 1M-token KV cache cannot
fit under any configuration this project could reasonably use.

This matters because the honest, achievable substitute is retrieval: keep
run history and project files indexed with local embeddings in SQLite, and
inject only the handful of chunks that are actually relevant to the current
goal — typically 5–10 chunks of a few hundred tokens each, not the entire
history. This is not a downgrade dressed up as a feature; it's the correct
engineering response to a real hardware ceiling, and it keeps the project's
SQLite-first design intact rather than bolting on a separate vector
database.

## Files likely touched

```text
memory/                        (new top-level package)
memory/embeddings.py           (new — local embedding calls via Ollama)
memory/chunking.py             (new — text chunking)
memory/indexer.py              (new — indexes runs and project files)
memory/retriever.py            (new — hybrid FTS5 + vector search)
orchestrator/database.py       (add memory_chunks table and FTS5 index)
config/models.yaml              (add a "memory" section, opt-in)
requirements.txt                (add sqlite-vec)
tests/test_memory.py            (new)
```

Files to inspect first (read-only):

```text
orchestrator/database.py
orchestrator/adapters.py
orchestrator/config_loader.py
run.py
```

## Exact implementation instructions

1. Create the branch:

```bash
cd /Users/andyyaro/Downloads/local-ai-orchestrator
git checkout main
git checkout -b phase-9-retrieval-memory
```

2. Add a `memory` section to `config/models.yaml`, opt-in and off by
   default — retrieval changes what context the model sees, and that should
   never happen silently:

```yaml
memory:
  retrieval_enabled: false
  embedding_model: "nomic-embed-text"
  top_k: 5
  chunk_size_tokens: 512
```

3. Add `sqlite-vec` to `requirements.txt`. This is a loadable SQLite
   extension with Python bindings — it is not automatically available just
   because SQLite ships with Python, so it must be installed explicitly.
   Design `memory/store.py` (or the relevant part of
   `orchestrator/database.py`) to **fail gracefully** if the extension can't
   load on a given machine: attempt `conn.enable_load_extension(True)` and
   load it, and if that raises, fall back to a pure-Python brute-force
   cosine similarity over stored embeddings instead of crashing. At the
   scale of one person's run history and project files (thousands, not
   millions, of chunks) brute-force search is genuinely fast enough — don't
   treat the fallback as a lesser-quality hack, it's a legitimate design
   choice at this scale.

4. Create `memory/embeddings.py`:

   - `embed(text: str, model: str | None = None) -> list[float]` — calls
     Ollama's dedicated embeddings endpoint (`/api/embeddings`, distinct
     from the `/api/generate` endpoint `OllamaAdapter` already uses) with
     the configured `embedding_model`. This needs its own small HTTP call
     using `get_ollama_base_url()` from `orchestrator/config_loader.py` —
     it does not fit `ModelAdapter`'s `call()` interface, since it returns a
     vector, not text, so don't force it into that abstraction.
   - Raise a clear error (not a silent empty vector) if the embedding model
     isn't pulled locally — mirroring the "never auto-download" rule: the
     error message should say exactly what to run
     (`ollama pull nomic-embed-text`), and the guide's install steps should
     tell you to run that yourself before using retrieval, never have code
     run it for you.

5. Create `memory/chunking.py`:

   - `chunk_text(text: str, chunk_size_tokens: int = 512) -> list[str]` — a
     simple, documented chunker (splitting on paragraph boundaries, then
     merging small paragraphs up to the target size) approximating "tokens"
     by word count. Document that this is an approximation, not real
     tokenization, since exact tokenization varies by model.

6. Add a `memory_chunks` table to `orchestrator/database.py`'s `SCHEMA`,
   plus an FTS5 virtual table for keyword search:

```sql
CREATE TABLE IF NOT EXISTS memory_chunks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT    NOT NULL,   -- 'run' or 'project_file'
    source_ref  TEXT    NOT NULL,   -- run_id or file path
    chunk_text  TEXT    NOT NULL,
    embedding   BLOB,
    created_at  TEXT    NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS memory_chunks_fts
USING fts5(chunk_text, content='memory_chunks', content_rowid='id');
```

   Store embeddings as packed floats (Python's `struct` module,
   `struct.pack(f"{len(vec)}f", *vec)`) in the `embedding` BLOB column —
   this keeps the database a single file with no external vector store
   dependency, consistent with the project's existing SQLite-only design.

7. Create `memory/indexer.py`:

   - `index_run(run_id: int)` — loads the run's `final_output` (already in
     the `runs` table from `orchestrator/database.py`), chunks it, embeds
     each chunk, and inserts rows into `memory_chunks` with
     `source_type="run"` and `source_ref=str(run_id)`.
   - `index_project_file(path: str)` — same, for a project file (for
     example, indexing `README.md` or files under `docs/`) with
     `source_type="project_file"`.
   - `summarize_run(run_id: int) -> str` — a short, model-generated summary
     of a past run's goal and outcome (this is the one place in this phase
     that does call a local model — a cheap one, like the `fast` profile's
     role model — since summarization is a real generation task, not a
     deterministic operation). Store the summary alongside the run so old
     runs can be represented compactly ("reflection memory") instead of
     re-indexing their full transcripts.

8. Create `memory/retriever.py`:

   - `keyword_search(query: str, k: int) -> list[dict]` — BM25-ranked
     search via the `memory_chunks_fts` virtual table.
   - `vector_search(query: str, k: int) -> list[dict]` — embeds the query
     with `embed()` and ranks stored chunks by cosine similarity (via
     sqlite-vec if it loaded, or the brute-force fallback otherwise).
   - `hybrid_search(query: str, k: int) -> list[dict]` — combines both
     result sets (a simple, documented approach like reciprocal rank fusion
     or a normalized weighted sum is enough — don't over-engineer the
     re-ranking) and returns the top `k` merged results.
   - `retrieve_context(goal: str, k: int | None = None) -> str` — the single
     entry point the pipeline calls: runs `hybrid_search`, formats the top
     chunks into a clearly-labeled context block (e.g. `"RELEVANT CONTEXT
     FROM PRIOR RUNS:\n..."`), and returns it as a string ready to prepend
     to a prompt. Keep injected context to the configured `top_k` chunks —
     never "just add everything that matched," since that reintroduces the
     unbounded-context problem this phase exists to avoid.

9. Wire `retrieve_context()` into `run.py`, gated by
   `memory.retrieval_enabled` (default `false`): if enabled, call it once
   after the Supervisor step and prepend its output to the Planner/Builder
   prompt inputs. Do the same in `orchestrator/graph.py` if that pipeline is
   still being kept in parity (check Phase 0's finding on this).

## Tests to add

Create `tests/test_memory.py` covering:

- `chunk_text` splits a known multi-paragraph string into the expected
  number of chunks near the target size, and handles a string shorter than
  one chunk without erroring.
- `keyword_search` and `vector_search` each return the expected top result
  for a small, hand-constructed set of indexed chunks — use a fake,
  deterministic embedding function in tests (for example, a hash-based
  vector) rather than calling the real `nomic-embed-text` model, so the
  test suite never needs Ollama running.
- `hybrid_search` returns a sensibly merged top-k list combining both
  signals, not just one or the other.
- The sqlite-vec-unavailable fallback path is exercised directly (force it
  by mocking the extension load failure) and still produces correct
  similarity ordering via the brute-force path.
- `retrieve_context` respects the configured `top_k` and never returns more
  chunks than requested.

## Commands to run

```bash
ruff check .
pytest tests/test_memory.py -v
pytest tests/ -v
```

## Expected output

- `tests/test_memory.py` passes without requiring Ollama or a real
  embedding model to be running.
- The full `tests/` suite still passes.
- With `memory.retrieval_enabled: true` and `nomic-embed-text` pulled
  locally, running the pipeline on a goal related to a prior run's topic
  shows a "RELEVANT CONTEXT FROM PRIOR RUNS" block in the Builder's prompt
  (visible in `runs/<timestamp>/` artifacts or logs), sized to `top_k`
  chunks, not the full history.

## If it fails

- `sqlite-vec` fails to load on your machine: confirm the fallback path
  actually engages rather than crashing — this is exactly the scenario step
  3 designs for; if it crashes instead of falling back, that's the bug to
  fix, not a reason to require the extension.
- Retrieval returns irrelevant chunks: check `hybrid_search`'s merge
  weighting — a common issue is one signal (usually keyword search)
  dominating because its scores aren't normalized to the same scale as the
  vector similarity scores before combining.
- The embedding call fails with a connection error: confirm
  `nomic-embed-text` is actually pulled (`ollama list`) before assuming the
  code is broken — this phase never pulls it for you.

## Rollback plan

Retrieval is entirely opt-in via `memory.retrieval_enabled`. If it produces
worse results than no retrieval at all, the immediate fix is setting that
flag back to `false` — no code change required. To remove the phase
entirely:

```bash
git log --oneline -10
git revert -m 1 <merge-commit-sha>
```

Or, if not yet merged:

```bash
git checkout main
git branch -D phase-9-retrieval-memory
```

## Commit suggestion

```text
feat: add local embedding-based retrieval memory, off by default
```

## Done when

```text
The system can retrieve relevant previous run context without stuffing
everything into the prompt: memory_chunks and its FTS5 index exist in
SQLite, hybrid search returns a sensible top-k result set backed by tests
that don't require a real embedding model, and retrieval only activates
when memory.retrieval_enabled is explicitly set to true.
```

## Claude Code phase prompt

```text
You are working in /Users/andyyaro/Downloads/local-ai-orchestrator.

Implement only Phase 9: retrieval and long-context-equivalent memory.

Before editing, run:
git status --short
git branch --show-current

Then inspect these files (read-only, do not edit yet):
- orchestrator/database.py
- orchestrator/adapters.py
- orchestrator/config_loader.py
- run.py

Implement the following:
1. Add a "memory" section to config/models.yaml with retrieval_enabled:
   false, embedding_model: "nomic-embed-text", top_k: 5,
   chunk_size_tokens: 512.
2. Add sqlite-vec to requirements.txt. Design the vector storage/search
   code to fall back to a pure-Python brute-force cosine similarity search
   if the sqlite-vec extension fails to load -- never crash if it's
   missing.
3. Create memory/embeddings.py with embed(text, model) calling Ollama's
   /api/embeddings endpoint directly (not through ModelAdapter). Raise a
   clear error naming the exact `ollama pull nomic-embed-text` command if
   the model isn't available -- never pull it automatically.
4. Create memory/chunking.py with chunk_text(text, chunk_size_tokens).
5. Add a memory_chunks table and an fts5 virtual table to
   orchestrator/database.py's SCHEMA, storing embeddings as packed-float
   BLOBs.
6. Create memory/indexer.py: index_run(run_id), index_project_file(path),
   summarize_run(run_id) (this one may call a cheap local model for
   summarization).
7. Create memory/retriever.py: keyword_search, vector_search,
   hybrid_search, and retrieve_context(goal, k) as the single pipeline
   entry point, capped strictly at top_k chunks.
8. Wire retrieve_context() into run.py, gated by memory.retrieval_enabled
   (default false), prepending its output to the Planner/Builder prompt
   inputs only when enabled.

Create tests/test_memory.py using a fake, deterministic embedding function
in tests -- never call the real nomic-embed-text model or require Ollama
running. Cover chunk_text, keyword_search, vector_search, hybrid_search,
the sqlite-vec-unavailable fallback path, and retrieve_context's top_k cap.

Do not modify any file outside this scope.
Do not enable memory.retrieval_enabled by default.
Do not enable cloud calls or change the active provider.
Do not run `ollama pull` or download any model.
Do not tag a release or bump a version number.
Do not merge to main or push to a remote unless explicitly told to in this
session.
Do not commit anything under runs/, logs/, .venv/, or .env.

After editing, run:
- ruff check .
- pytest tests/test_memory.py -v
- pytest tests/ -v
- git status --short

Stop after reporting:
1. Files changed
2. Tests run and their results
3. Whether the sqlite-vec extension loaded successfully in this
   environment or the brute-force fallback was used
4. Any remaining risks or TODOs
5. A suggested commit message
```
