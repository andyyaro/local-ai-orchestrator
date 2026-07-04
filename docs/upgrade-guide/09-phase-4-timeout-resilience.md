# 09 — Phase 4: Timeout and Resilience

## Goal

Handle slow or failed model calls intelligently: classify *why* a call
failed, retry only true transient failures once, fall back to a smaller
local model on timeout/overload instead of repeating the identical call, and
never hard-kill the process on final failure without saving partial work.

## Why it matters

Repo inspection found the actual anti-pattern this phase exists to fix, in
`agents/base_agent.py`'s `call_model()`:

```python
except RuntimeError as e:
    if attempt <= self.max_retries:
        print(f"  [WARN] {self.role} attempt {attempt} failed: {e}. Retrying...")
        time.sleep(3)
        continue
    self._fatal(str(e))
```

This retries the *identical* call, with a flat 3-second sleep, regardless of
whether the failure was a dropped connection, a timeout, or an HTTP error —
and `orchestrator/adapters.py`'s `OllamaAdapter.call()` collapses all three
into a generic `RuntimeError`, so `call_model()` cannot even tell them apart.
On final failure, `_fatal()` calls `sys.exit(1)` directly from inside the
agent layer, which kills the whole process without giving `run.py` a chance
to save the partial run the way it already does for `KeyboardInterrupt`.

This matters because a local Ollama timeout is not the same kind of failure
as a cloud API rate limit, and treating them the same wastes real time on
your Mac. Do not use blind exponential backoff for local Ollama timeouts.
Exponential backoff with jitter exists to handle *shared-server contention*
— many clients hitting one rate-limited endpoint, where waiting longer genuinely
helps the queue drain. A local Ollama call has exactly one client (you) and
one likely cause: the model is still loading, the machine is under memory
pressure, or the model is just slow at this prompt length. Retrying the
identical call after a fixed sleep does not address any of those causes — it
just repeats the same wait. The two failure classes need two different
responses:

- **Local Ollama slow/timeout/OOM** → classify the failure, retry at most
  once for a truly transient case (e.g. a dropped connection), and otherwise
  fall back to a smaller, faster local model rather than repeating the same
  call.
- **Cloud/API 429 (rate limited) or 503 (unavailable)** → exponential
  backoff with jitter is the correct, standard response here — but this repo
  has no working cloud adapter yet (Phase 7), so this phase only needs to
  build the branch for it, not exercise it for real.

## Files likely touched

```text
orchestrator/resilience.py   (new)
tests/test_resilience.py     (new)
orchestrator/adapters.py      (raise typed exceptions instead of generic RuntimeError)
agents/base_agent.py          (replace blind retry loop with resilience-aware call)
run.py                        (catch fatal resilience errors, save partial run, matching KeyboardInterrupt handling)
config/models.yaml             (add timeouts and fallback_model settings)
```

Files to inspect first (read-only):

```text
orchestrator/adapters.py
agents/base_agent.py
orchestrator/config_loader.py
config/models.yaml
run.py
```

## Exact implementation instructions

1. Create the branch:

```bash
cd /Users/andyyaro/Downloads/local-ai-orchestrator
git checkout main
git checkout -b phase-4-timeout-resilience
```

2. Add per-model-size timeout budgets and a fallback model to
   `config/models.yaml`:

```yaml
resilience:
  timeouts:
    default: 600
    small: 120    # e.g. llama3.2:3b class
    medium: 300   # e.g. llama3.1:8b, gemma3:12b class
    large: 600    # e.g. qwen2.5:14b, qwen2.5-coder:14b, phi4:14b class
  fallback_model: "llama3.2:3b"
  max_local_retries: 1
  cloud_backoff:
    base_seconds: 1
    max_seconds: 30
    max_retries: 4
```

   Add `get_resilience_config() -> dict` to `orchestrator/config_loader.py`,
   following the existing caching pattern.

3. In `orchestrator/adapters.py`, replace the generic `RuntimeError` raises
   in `OllamaAdapter.call()` with typed exceptions so the caller doesn't have
   to parse error message strings to know what happened. Define these in the
   new `orchestrator/resilience.py` (adapters.py can import from it without
   creating a circular import, since resilience.py does not need adapters.py):

   - `ModelCallError` (base class)
   - `ModelConnectionError(ModelCallError)` — replaces the
     `requests.exceptions.ConnectionError` branch.
   - `ModelTimeoutError(ModelCallError)` — replaces the
     `requests.exceptions.Timeout` branch.
   - `ModelHTTPError(ModelCallError)` — replaces the
     `requests.exceptions.HTTPError` branch.

   Keep the existing, already-good human-readable messages
   ("Cannot connect to Ollama at...", "Ollama timed out after...") — only the
   exception *type* changes, not the wording.

4. In `orchestrator/resilience.py`, implement the classification and
   decision logic:

   - `classify_failure(exc: Exception) -> str` — returns `"connection"`,
     `"timeout"`, `"http"`, or `"unknown"` based on the exception type from
     step 3.
   - `get_timeout_for_model(model: str) -> int` — maps a model name to a
     size class (a simple heuristic on the model string, e.g. matching
     `"3b"`/`"1b"` → `small`, `"7b"`/`"8b"`/`"12b"` → `medium`, `"14b"`/`"13b"`
     and above → `large`) and returns the matching value from
     `resilience.timeouts` in config. Document the size-matching heuristic
     clearly since it's a judgment call, and default to `resilience.timeouts.default`
     for anything unmatched.
   - `call_with_resilience(model: str, prompt: str, temperature: float, num_ctx: int, role: str) -> str`
     — the new entry point that replaces `BaseAgent.call_model()`'s inner
     loop. Behavior:
     - First attempt: call the adapter with `get_timeout_for_model(model)`
       as the effective timeout (adapters.py's `OllamaAdapter` should accept
       a per-call timeout override rather than only using the global
       `request_timeout` from config).
     - On `ModelConnectionError` (a plausibly transient failure — the
       server hiccuped, not that the model itself is slow): retry once,
       with a short fixed wait (2–3 seconds is fine here, since this really
       is "try again briefly," not "the model is overloaded").
     - On `ModelTimeoutError` (the model itself is too slow, likely due to
       memory pressure, prompt length, or genuine model slowness): do
       **not** retry the identical call. Instead, fall back once to
       `resilience.fallback_model` and log that a fallback occurred. If the
       fallback model *also* times out, fail fast — do not chain further
       fallbacks.
     - On `ModelHTTPError`: fail fast for 4xx-style client errors (these
       indicate a bad request, not a transient condition); this phase's
       cloud-backoff branch (exponential backoff with jitter, capped at
       `resilience.cloud_backoff.max_retries`) only applies once Phase 7
       adds a real cloud adapter that can actually return 429/503 — build
       the branch now, but it will be unreachable via Ollama today, and
       that's fine.
     - Raise a new `FatalModelError(ModelCallError)` if all applicable
       retries/fallbacks are exhausted, carrying a clear message about what
       was tried.

5. Update `agents/base_agent.py`'s `call_model()` to call
   `orchestrator.resilience.call_with_resilience()` instead of its current
   inline retry loop. Remove the `sys.exit(1)` call from `_fatal()` — instead
   let `FatalModelError` propagate up out of the agent call.

6. In `run.py`, wrap the `run_pipeline()` call in `main()` with a second
   `except` clause (alongside the existing `KeyboardInterrupt` handler) that
   catches `FatalModelError`, prints a clear message, and confirms the
   partial run directory (`run_dir`) still has whatever artifacts were saved
   before the failure — mirroring exactly how `KeyboardInterrupt` is already
   handled, so a model failure and a user-initiated stop behave consistently.

7. Optional, lower priority within this phase — implement only if the above
   is solid and tested first: a `--resume <run_dir>` CLI flag that, given a
   `runs/<timestamp>/` directory from a prior failed or interrupted run,
   reloads the last saved draft (`best_draft.txt` or the highest-numbered
   `loopNN_fixer.txt`) and continues the loop from there rather than
   restarting from the Supervisor. This is explicitly a stretch goal — if you
   run out of time in this phase, stop after step 6 and note resume-from-
   artifact as deferred, rather than shipping a half-working `--resume` flag.

## Tests to add

Create `tests/test_resilience.py` covering:

- `classify_failure` correctly identifies each of `ModelConnectionError`,
  `ModelTimeoutError`, `ModelHTTPError`, and an unrelated exception type
  (`"unknown"`).
- `get_timeout_for_model` returns the expected size-class timeout for
  representative model names (e.g. `"llama3.2:3b"` → small, `"qwen2.5:14b"`
  → large) and the default for an unrecognized name.
- `call_with_resilience`, using a fake adapter you construct in the test
  (not a real Ollama call): a `ModelConnectionError` on the first call and
  success on the second results in exactly one retry and a successful
  return. A `ModelTimeoutError` on the first call results in exactly one
  call to the fallback model, not a repeated call to the original model. A
  `ModelTimeoutError` on both the original and fallback model raises
  `FatalModelError` rather than retrying indefinitely.
- No test should sleep for real multi-second delays — use a short,
  test-only wait value or mock `time.sleep` so the suite stays fast.

## Verification

Run the checks below and confirm they match the expected output that follows.

## Commands to run

```bash
ruff check .
pytest tests/test_resilience.py -v
pytest tests/ -v
```

## Expected output

- `tests/test_resilience.py` passes, with no real multi-second sleeps
  slowing down the suite.
- The full `tests/` suite still passes.
- A manual test where you stop Ollama mid-run (`osascript -e 'quit app
  "Ollama"'` or quitting it from the menu bar) shows the pipeline printing a
  clear connection-failure message, attempting exactly one retry, and then
  either succeeding (if you restart Ollama in time) or failing cleanly with
  the partial run directory intact — not a raw Python traceback and not a
  silent hang.

## If it fails

- The fallback model also isn't available locally, so the fallback attempt
  itself raises a connection error: this is expected — `call_with_resilience`
  should surface this as `FatalModelError` with a message naming both models
  that failed, not swallow the second failure silently.
- Existing agent tests break because `call_model()`'s signature or behavior
  changed: check whether any test relied on the old `sys.exit(1)` behavior on
  failure — update those tests to expect `FatalModelError` instead, since the
  hard-exit behavior is exactly what this phase removes.
- The pipeline seems to hang instead of timing out: confirm
  `get_timeout_for_model()` is actually being passed through to
  `OllamaAdapter.call()`'s `requests.post(..., timeout=...)` argument — a
  common mistake is computing the right timeout value but not threading it
  into the actual HTTP call.

## Rollback plan

If the fallback-to-smaller-model behavior produces confusing results (for
example, silently degrading output quality without it being obvious in the
run summary), revert the phase:

```bash
git log --oneline -10
git revert -m 1 <merge-commit-sha>
```

Or, if not yet merged:

```bash
git checkout main
git branch -D phase-4-timeout-resilience
```

As an interim safety valve short of a full revert, you can set
`resilience.max_local_retries: 0` in `config/models.yaml` to disable the
retry-once behavior while keeping the typed-exception classification and
clean failure handling from steps 3–6.

## Commit suggestion

```text
feat: add failure classification, model fallback, and clean failure handling
```

## Done when

```text
The system does not repeatedly retry the same slow local call without
changing strategy: a connection error retries once, a timeout falls back to
a smaller model once, and a final unrecoverable failure raises a typed
exception that run.py catches and handles by preserving the partial run
directory rather than a hard process exit.
```

## Claude Code phase prompt

```text
You are working in /Users/andyyaro/Downloads/local-ai-orchestrator.

Implement only Phase 4: timeout and resilience.

Before editing, run:
git status --short
git branch --show-current

Then inspect these files (read-only, do not edit yet):
- orchestrator/adapters.py
- agents/base_agent.py
- orchestrator/config_loader.py
- config/models.yaml
- run.py

Implement the following:
1. Add a "resilience" section to config/models.yaml (timeouts by size class,
   fallback_model, max_local_retries, cloud_backoff settings) and a
   get_resilience_config() getter in orchestrator/config_loader.py.
2. In orchestrator/adapters.py, replace OllamaAdapter.call()'s generic
   RuntimeError raises with typed exceptions (ModelConnectionError,
   ModelTimeoutError, ModelHTTPError, all subclassing ModelCallError),
   defined in a new orchestrator/resilience.py. Keep the existing error
   messages, only change the exception types. Make OllamaAdapter.call()
   accept a per-call timeout override instead of only using the global
   config timeout.
3. In orchestrator/resilience.py, implement classify_failure(exc),
   get_timeout_for_model(model) using a size-class heuristic, and
   call_with_resilience(model, prompt, temperature, num_ctx, role) that:
   retries once (short fixed wait) on ModelConnectionError; falls back once
   to resilience.fallback_model on ModelTimeoutError instead of retrying
   the same model; fails fast on ModelHTTPError with a cloud-backoff branch
   present but not required to be exercised (Ollama won't trigger it today);
   raises FatalModelError if all retries/fallbacks are exhausted.
4. Update agents/base_agent.py's call_model() to use
   call_with_resilience() instead of its current inline retry loop with
   time.sleep(3) and sys.exit(1). Remove the sys.exit(1) call entirely —
   let FatalModelError propagate.
5. In run.py's main(), add an except clause for FatalModelError alongside
   the existing KeyboardInterrupt handler, so a model failure prints a
   clear message and preserves the partial run_dir the same way an
   interrupted run already does.
6. Do NOT implement the optional --resume flag in this phase unless steps
   1-5 are complete and tested — if you run out of scope, stop and report
   --resume as deferred rather than shipping it half-finished.

Create tests/test_resilience.py using a fake adapter (do not call real
Ollama in tests) covering classify_failure, get_timeout_for_model, and
call_with_resilience's retry/fallback/fatal-error behavior. Do not use real
multi-second sleeps in tests — mock time.sleep or use a short test-only
wait value.

Do not modify any file outside this scope.
Do not enable cloud calls or change the active provider.
Do not run `ollama pull` or download any model.
Do not tag a release or bump a version number.
Do not merge to main or push to a remote unless explicitly told to in this
session.
Do not commit anything under runs/, logs/, .venv/, or .env.

After editing, run:
- ruff check .
- pytest tests/test_resilience.py -v
- pytest tests/ -v
- git status --short

Stop after reporting:
1. Files changed
2. Tests run and their results
3. Any remaining risks or TODOs (including whether --resume was deferred)
4. A suggested commit message
```
