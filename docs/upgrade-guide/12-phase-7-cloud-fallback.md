# 12 — Phase 7: Optional Cloud Fallback Scaffolding

## v2.0 scope reminder

This is the first v2.0 phase. Do not start it until Phases 0–6 are merged and
stable — cloud fallback adds real risk (secrets, cost, external calls) on top
of a pipeline that should already be fast, validated, and measured. If you
haven't finished the v1.1 phases, stop here and go back.

## Goal

Add the *architecture* for optional cloud fallback — a provider adapter,
a cloud policy, a cost tracker, and a privacy guard — without ever enabling a
real external call by default. This phase is scaffolding, not activation.

## Why it matters

`orchestrator/adapters.py` already has `OpenAIAdapter` and `AnthropicAdapter`
classes, but both are literal placeholders that just `raise
NotImplementedError`. The project's own README still lists "Add optional
OpenAI or Anthropic provider support through config" as an unchecked planned
improvement. This matters because cloud fallback is real leverage — a single
frontier-model call on a narrow, verifiable step (scoring a draft, polishing
a final output) can meaningfully raise output quality without needing your
Mac to somehow become a frontier-model machine — but only if it's built with
real guardrails from day one: off by default, opt-in per run, human-approved
per call, cost-capped, and scanned for secrets before anything leaves your
machine. Building the excitement (a working cloud call) before the
guardrails (budget, privacy, approval) is exactly backwards and is not what
this phase does.

The cloud fallback research report (`docs/research/compass_artifact_wf-f11fd32d-aa8a-4145-ba84-db3f3fd5d412_text_markdown.md`)
frames this correctly: fallback should be an **off-by-default, per-role,
per-trigger, human-gated escalation layer** that sends the smallest possible
sanitized payload for a single step — not the whole task, not the whole
repo — to one frontier model. Model names, pricing, and provider specifics
in that report should be re-verified against the provider's current
published pricing before you rely on any cost estimate in production;
treat the numbers in this phase's config as a starting point you confirm,
not a fact to trust blindly.

## Files likely touched

```text
orchestrator/cloud_policy.py    (new)
orchestrator/cost_tracker.py    (new)
orchestrator/privacy_guard.py   (new)
orchestrator/adapters.py         (implement AnthropicAdapter for real, gated; add a MockCloudAdapter for tests)
orchestrator/database.py         (add cloud_calls table)
tests/test_cloud_policy.py       (new)
tests/test_cost_tracker.py       (new)
tests/test_privacy_guard.py      (new)
config/models.yaml                (add a "cloud" section)
run.py                            (optional, human-gated escalation call site)
```

Files to inspect first (read-only):

```text
orchestrator/adapters.py
orchestrator/database.py
orchestrator/config_loader.py
config/models.yaml
run.py
docs/research/compass_artifact_wf-f11fd32d-aa8a-4145-ba84-db3f3fd5d412_text_markdown.md
```

Streamlit display of cloud status/approval/cost is deferred to Phase 8
(`13-phase-8-streamlit-updates.md`, planned) — this phase only needs the
policy, tracking, and privacy logic to exist and be correct, not to have a
UI. Note this overlap so you don't expect a UI change here.

## Exact implementation instructions

1. Create the branch:

```bash
cd /Users/andyyaro/Downloads/local-ai-orchestrator
git checkout main
git checkout -b phase-7-cloud-fallback
```

2. Add a `cloud` section to `config/models.yaml`. `enabled: false` is the
   only value that matters on first read — everything else is inert until
   that's flipped, and even then, per-call approval (step 5) still gates
   every individual request:

```yaml
cloud:
  enabled: false
  provider: anthropic
  model: "claude-sonnet-5"
  allowed_roles: ["judge", "synthesizer"]
  require_approval: true
  send_full_project_state: false
  budget:
    per_run_usd: 0.25
    daily_usd: 2.00
    monthly_usd: 20.00
    block_over_budget: true
  pricing:
    input_per_million_usd: 2.00
    output_per_million_usd: 10.00
```

   ⚠️ `send_full_project_state` must default to `false` and this phase must
   never implement a path that ignores it — the whole point of the privacy
   guard (step 4) is that only a minimal, role-specific payload is built,
   never the full repo or `.env` contents.

3. Create `orchestrator/cloud_policy.py`:

   - `is_cloud_enabled() -> bool` — reads `cloud.enabled` from config.
     Returns `False` immediately if `provider: ollama` is still set at the
     top level, as a second independent check (defense in depth: two config
     flags both have to agree before any cloud path is even considered).
   - `is_role_allowed(role: str) -> bool` — checks `role` against
     `cloud.allowed_roles`. Only `judge` and `synthesizer` are allowed by
     default; any other role must be explicitly added to config by you,
     never silently expanded by code.
   - `should_attempt_cloud(role: str) -> bool` — combines the two checks
     above. This is the single function every call site should check before
     doing anything else cloud-related.
   - `request_human_approval(role: str, payload_preview: str, estimated_cost_usd: float) -> bool`
     — prints the exact payload that would be sent (in full, not truncated
     in a way that could hide something) and the estimated cost, then reads
     a `y`/`n` confirmation from the terminal. Return `False` on anything
     other than an explicit `y`. This function must never be called from a
     non-interactive context (CI, an automated script) — document that
     constraint directly in the docstring.

4. Create `orchestrator/privacy_guard.py`:

   - `scan_for_secrets(text: str) -> list[str]` — regex-based scan for
     obvious secret patterns (API key-shaped strings, `sk-...`,
     `ANTHROPIC_API_KEY=`, AWS-style keys, bearer tokens, anything matching
     a pattern in the existing `.env` file's key names). Return a list of
     findings (empty if clean).
   - `build_minimal_payload(role: str, goal: str, draft: str, extra: dict | None = None) -> str`
     — constructs *only* what that specific role needs. For `judge`: the
     goal, the draft being scored, and the scoring rubric text already used
     locally — nothing else. For `synthesizer`: the goal and the best draft
     — nothing else. Never include file paths, `.env` contents, other
     agents' raw intermediate output beyond what's relevant, or run history
     from other runs.
   - `guard_payload(role: str, payload: str) -> str` — calls
     `scan_for_secrets()` on the built payload and raises a clear
     `PrivacyGuardError` if anything is found, rather than silently
     redacting and sending a possibly-still-sensitive payload. Fail closed,
     not open.

5. Create `orchestrator/cost_tracker.py`:

   - `estimate_cost(input_tokens: int, output_tokens: int) -> float` — uses
     `cloud.pricing` from config. Document that this is an estimate, not
     exact, since real tokenization differs slightly from any local
     approximation you use to count tokens.
   - `get_spend(period: str) -> float` (`period` is `"daily"` or
     `"monthly"`) — sums `cost_usd` from the new `cloud_calls` table for the
     relevant window.
   - `check_budget(estimated_cost_usd: float) -> bool` — returns `False` if
     adding this call would exceed `per_run_usd`, `daily_usd`, or
     `monthly_usd`, and `cloud.budget.block_over_budget` is `true`. This is
     the function that actually blocks an over-budget call — it must be
     checked *before* `request_human_approval()`, so you're never even asked
     to approve a call that's already over budget.
   - `record_call(run_id, role, model, input_tokens, output_tokens, cost_usd, approved: bool)`
     — writes a row to the new `cloud_calls` table.

6. Add a `cloud_calls` table to `orchestrator/database.py`'s `SCHEMA`,
   following the existing `runs`/`iterations` table style:

```sql
CREATE TABLE IF NOT EXISTS cloud_calls (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL,
    run_id          INTEGER REFERENCES runs(id) ON DELETE CASCADE,
    role            TEXT    NOT NULL,
    provider        TEXT    NOT NULL,
    model           TEXT    NOT NULL,
    input_tokens    INTEGER DEFAULT 0,
    output_tokens   INTEGER DEFAULT 0,
    cost_usd        REAL    DEFAULT 0,
    approved_by_user INTEGER DEFAULT 0
);
```

7. ⚠️ **Before implementing a real adapter, verify the model ID and pricing
   directly against the provider's own official documentation** —
   `config/models.yaml`'s `cloud.model: "claude-sonnet-5"` and the
   `cloud.pricing` block in step 2 above are drawn from the research report
   at `docs/research/compass_artifact_wf-f11fd32d-...md`, and that report's
   own text already flags that its model names and prices should be
   re-verified, not trusted as fact. A model ID or price that's wrong isn't
   a cosmetic bug here — it's either a broken API call or an incorrect cost
   estimate feeding directly into `cost_tracker.py`'s budget enforcement. Do
   not copy the model ID or pricing numbers from this guide, this research
   report, or any other secondhand source into real code without checking
   them yourself against the provider's current published docs first.

   **If you have not personally verified the current model ID and pricing
   against the provider's official documentation, stop at the
   `MockCloudAdapter` and do not implement a real adapter in this session.**
   Report back that real-adapter implementation is deferred pending
   verification, rather than shipping a call that might target a
   deprecated model ID or budget-check against stale prices.

   Once verified, implement `AnthropicAdapter.call()` in
   `orchestrator/adapters.py` for real, but only ever invoked after steps
   3–6 have already passed (policy allowed, privacy guard passed, budget
   check passed, human approved). Read the API key from `.env` (already
   git-ignored) via the existing project convention — never hardcode it,
   never log it, never include it in any payload preview. Also add a
   `MockCloudAdapter` (in `adapters.py` or a test-only module) that returns
   a canned, deterministic response with no network call at all — this is
   what every test and CI use, never the real adapter.

8. Wire an optional escalation call site into `run.py`. Keep this narrow: a
   new `--allow-cloud` CLI flag (default off) is required *in addition to*
   `cloud.enabled: true` in config *in addition to* passing
   `should_attempt_cloud()` *in addition to* the budget check *in addition
   to* interactive approval — all five conditions must hold before a real
   cloud call happens for a given role's step. If any one is missing, the
   pipeline proceeds using only the local model result, exactly as it does
   today.

## Tests to add

- `tests/test_cloud_policy.py`: `is_cloud_enabled()` is `False` by default
  against the shipped config; `is_role_allowed()` returns `True` only for
  `judge`/`synthesizer` by default and `False` for any other role;
  `should_attempt_cloud()` requires both checks to pass.
- `tests/test_cost_tracker.py`: `estimate_cost()` matches a hand-computed
  value for known token counts and pricing; `check_budget()` correctly
  blocks a call that would exceed `per_run_usd`/`daily_usd`/`monthly_usd`
  using an in-memory or temp SQLite database seeded with prior `cloud_calls`
  rows.
- `tests/test_privacy_guard.py`: `scan_for_secrets()` catches an
  obviously-shaped fake API key string; `build_minimal_payload()` for the
  `judge` role does not include an injected fake `.env`-style secret placed
  elsewhere in the run's context, proving the minimal-payload construction
  actually excludes it rather than merely not mentioning it explicitly;
  `guard_payload()` raises `PrivacyGuardError` when a finding is present.
- All three test files must use `MockCloudAdapter` or no adapter at all —
  never a real network call, never a real API key, even one from a test
  fixture `.env`.

## Verification

Run the checks below and confirm they match the expected output that follows.

## Commands to run

```bash
ruff check .
pytest tests/test_cloud_policy.py tests/test_cost_tracker.py tests/test_privacy_guard.py -v
pytest tests/ -v
```

## Expected output

- All three new test files pass.
- The full `tests/` suite still passes.
- With `cloud.enabled: false` (the shipped default), running the pipeline
  normally shows no cloud-related output at all and makes no network call
  beyond Ollama.
- Manually setting `cloud.enabled: true`, passing `--allow-cloud`, and
  running a Judge step shows an exact payload preview and cost estimate
  printed to the terminal, and requires a literal `y` response before any
  real request is sent.

## If it fails

- A test accidentally makes a real network call: stop immediately — this
  means a test is using `AnthropicAdapter` directly instead of
  `MockCloudAdapter`. Fix the test before doing anything else; a test suite
  that can make real billed API calls is not safe to run in CI or by anyone
  else who clones this repo.
- `check_budget()` allows a call that should have been blocked: check the
  daily/monthly SQLite sum query — a common bug is querying across all
  timestamps instead of filtering to the current day/month window.
- The privacy guard misses an obvious secret: add that exact string as a new
  regression test case in `test_privacy_guard.py` before adjusting the
  regex, the same discipline used for the word-limit regex in Phase 2.

## Rollback plan

Since `cloud.enabled: false` is the default and every real call requires
five independent conditions to hold, the safest rollback if anything about
this phase feels wrong is simply confirming `cloud.enabled: false` and
never passing `--allow-cloud` — the scaffolding can sit unused indefinitely
without risk. To fully remove it:

```bash
git log --oneline -10
git revert -m 1 <merge-commit-sha>
```

Or, if not yet merged:

```bash
git checkout main
git branch -D phase-7-cloud-fallback
```

## Commit suggestion

```text
feat: add cloud fallback scaffolding (policy, privacy guard, cost tracker), off by default
```

## Done when

```text
Cloud fallback exists as safe scaffolding but no external API is called by
default: cloud.enabled is false in the shipped config, real cloud calls
require five independent conditions (config enabled, CLI flag, role
allow-list, budget check, human approval) all to hold, every test uses a
mock adapter with zero real network calls, and cloud_calls in SQLite gives
you a full audit trail of anything that ever does go out.
```

## Claude Code phase prompt

```text
You are working in /Users/andyyaro/Downloads/local-ai-orchestrator.

Implement only Phase 7: optional cloud fallback scaffolding.

Before editing, run:
git status --short
git branch --show-current

Then inspect these files (read-only, do not edit yet):
- orchestrator/adapters.py
- orchestrator/database.py
- orchestrator/config_loader.py
- config/models.yaml
- run.py

Implement the following:
1. Add a "cloud" section to config/models.yaml with enabled: false,
   allowed_roles: [judge, synthesizer], require_approval: true,
   send_full_project_state: false, a budget block (per_run_usd: 0.25,
   daily_usd: 2.00, monthly_usd: 20.00, block_over_budget: true), and a
   pricing block.
2. Create orchestrator/cloud_policy.py: is_cloud_enabled(),
   is_role_allowed(role), should_attempt_cloud(role), and
   request_human_approval(role, payload_preview, estimated_cost_usd) which
   prints the full payload and cost and requires a literal "y" response.
3. Create orchestrator/privacy_guard.py: scan_for_secrets(text),
   build_minimal_payload(role, goal, draft, extra=None) that includes only
   what that specific role needs (never full project state, never .env
   contents), and guard_payload(role, payload) that raises
   PrivacyGuardError if scan_for_secrets finds anything. Fail closed.
4. Create orchestrator/cost_tracker.py: estimate_cost(input_tokens,
   output_tokens), get_spend(period), check_budget(estimated_cost_usd), and
   record_call(...) writing to a new cloud_calls table.
5. Add a cloud_calls table to orchestrator/database.py's SCHEMA.
6. Add a MockCloudAdapter with a canned deterministic response and no
   network call, for tests only. Before implementing AnthropicAdapter.call()
   for real, verify the current model ID and pricing directly against the
   provider's official documentation -- do not copy the model ID or pricing
   numbers from this guide or the research report without checking them
   yourself first. If you have not verified them in this session, stop
   here: implement only MockCloudAdapter, do not implement a real
   AnthropicAdapter.call(), and report that real-adapter implementation is
   deferred pending verification. If you have verified them, implement
   AnthropicAdapter.call() for real in orchestrator/adapters.py, reading the
   API key only from .env, never logging or previewing it.
7. Add an --allow-cloud CLI flag to run.py (default off). A real cloud call
   must require ALL of: cloud.enabled true in config, --allow-cloud passed,
   should_attempt_cloud() true for that role, check_budget() passing, and
   request_human_approval() returning true. Missing any one falls back to
   using only the local model result.

Create tests/test_cloud_policy.py, tests/test_cost_tracker.py, and
tests/test_privacy_guard.py. All tests must use MockCloudAdapter or no
adapter at all -- never a real network call or real API key.

Do not modify any file outside this scope.
Do not set cloud.enabled to true in the committed config.
Do not make a real network call to any cloud provider during this session.
Do not run `ollama pull` or download any model.
Do not tag a release or bump a version number.
Do not merge to main or push to a remote unless explicitly told to in this
session.
Do not commit anything under runs/, logs/, .venv/, or .env.

After editing, run:
- ruff check .
- pytest tests/test_cloud_policy.py tests/test_cost_tracker.py tests/test_privacy_guard.py -v
- pytest tests/ -v
- git status --short

Stop after reporting:
1. Files changed
2. Tests run and their results
3. Confirmation that no real network call was made during implementation
   or testing
4. Any remaining risks or TODOs
5. A suggested commit message
```
