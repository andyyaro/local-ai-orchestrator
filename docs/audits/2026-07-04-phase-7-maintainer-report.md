# Phase 7 Maintainer Report — Optional Cloud Fallback Scaffolding

## Goal

Add the architecture for optional cloud fallback (provider adapter, cloud
policy, cost tracker, privacy guard) without ever enabling a real external
call by default. Scaffolding, not activation.

## What was built

1. **`config/models.yaml`** — new `cloud` section: `enabled: false`,
   `provider: anthropic`, `model: "claude-sonnet-5"`,
   `allowed_roles: ["judge", "synthesizer"]`, `require_approval: true`,
   `send_full_project_state: false`, a `budget` block
   (`per_run_usd: 0.25`, `daily_usd: 2.00`, `monthly_usd: 20.00`,
   `block_over_budget: true`), and a `pricing` block. Commented explicitly
   that the model ID and pricing are unverified placeholders.
2. **`orchestrator/config_loader.py`** — `get_cloud_config()` added,
   following the existing `get_resilience_config()` pattern.
3. **`orchestrator/cloud_policy.py`** (new) — `is_cloud_enabled()` (checks
   `cloud.enabled` AND that the top-level `provider` isn't `"ollama"`,
   two independent flags that both must agree), `is_role_allowed(role)`,
   `should_attempt_cloud(role)` (the single gate every call site must
   pass), and `request_human_approval(role, payload_preview,
   estimated_cost_usd)` (prints the full payload and cost, requires a
   literal `y`; docstring explicitly warns it must never run in a
   non-interactive context).
4. **`orchestrator/privacy_guard.py`** (new) — `scan_for_secrets(text)`
   (regex patterns for Anthropic/OpenAI-style keys, AWS access key IDs,
   bearer tokens, and `KEY_NAME=value` assignments for the provider key
   names this repo documents), `build_minimal_payload(role, goal, draft,
   extra=None)` (role-scoped: judge gets goal+draft+rubric, synthesizer
   gets goal+draft, anything else gets goal+draft only — extra keys not
   read for that role are silently dropped, not forwarded), and
   `guard_payload(role, payload)` (raises `PrivacyGuardError` fail-closed
   if anything is found).
5. **`orchestrator/cost_tracker.py`** (new) — `estimate_cost(input_tokens,
   output_tokens)` (from `cloud.pricing`), `get_spend(period)` (delegates
   to the new database query), `check_budget(estimated_cost_usd)` (checks
   `per_run_usd`/`daily_usd`/`monthly_usd`, returns `True` immediately if
   `block_over_budget` is `false`), and `record_call(...)` (writes to the
   new table via `orchestrator.database.save_cloud_call`).
6. **`orchestrator/database.py`** — added the `cloud_calls` table to
   `SCHEMA` exactly as specified in the guide, plus `save_cloud_call(...)`
   and `get_cloud_spend(period)` (sums `cost_usd` using an ISO-timestamp
   prefix match — `"2026-07-04"` for daily, `"2026-07"` for monthly —
   consistent with how `save_run` already stores timestamps).
7. **`orchestrator/adapters.py`** — added `get_cloud_adapter()` (selects
   by `cloud.provider`, independent of the main `provider` field) and
   `MockCloudAdapter` (canned deterministic response, records every call
   it receives, no network access at all — used by every test).
   `AnthropicAdapter.call()` **still raises `NotImplementedError`** — see
   "Real adapter deferred" below.
8. **`run.py`** — added `_maybe_escalate_to_cloud(role, goal, draft,
   allow_cloud, run_id=None, rubric="")`, a single helper that checks all
   five conditions in order (CLI flag → `should_attempt_cloud` →
   privacy guard → budget → human approval) and returns `None` the moment
   any one fails, falling back to the local result exactly as today. Added
   a `--allow-cloud` CLI flag (default off) and threaded `allow_cloud`
   through `run_pipeline()`. Wired **one** narrow call site: right after
   the Synthesizer produces its local output, `_maybe_escalate_to_cloud`
   is offered the chance to replace it — but since it can currently never
   get past the (intentionally unimplemented) adapter call, this can never
   actually change output in this session. Whatever `final_output` ends
   up being (local or, in the future, cloud) still passes through the
   exact same Phase 6b/6c constraint-validation guard already in place, so
   a cloud response could never bypass validation either.

## Real adapter deferred (per the guide's explicit instruction)

The guide states: *"If you have not personally verified the current model
ID and pricing against the provider's official documentation, stop at the
MockCloudAdapter and do not implement a real adapter in this session."*
This session did not verify `"claude-sonnet-5"` or the `$2.00`/`$10.00`
per-million-token pricing against Anthropic's current published
documentation (no external verification was performed, consistent with
this being an unattended, no-real-network-calls session). Per the guide's
explicit instruction, **`AnthropicAdapter.call()` was left exactly as it
was — a placeholder raising `NotImplementedError`** — with its docstring
updated to explain why, pointing at `MockCloudAdapter` for all testing and
development in the meantime. No `OpenAIAdapter` implementation was
attempted either, for the same reason (never verified). This means the
`--allow-cloud` flag and the escalation call site described above are
fully wired and tested (all five gate conditions), but even if a user
somehow got past every gate today, the final step would raise a clear
`NotImplementedError` (caught and printed, not crashed) rather than making
any real request.

## Tests added

- `tests/test_cloud_policy.py` (12 tests) — `is_cloud_enabled()` false
  against the real shipped config; both independent flags required
  (provider != ollama AND cloud.enabled); `is_role_allowed()` true only
  for judge/synthesizer by default, false for every other role, and
  respects an explicit config override; `should_attempt_cloud()` requires
  both checks; `request_human_approval()`'s exact `"y"`-only matching
  logic (via `monkeypatch.setattr("builtins.input", ...)` — never a real
  interactive call).
- `tests/test_cost_tracker.py` (9 tests) — `estimate_cost()` against
  hand-computed values; `check_budget()` blocking on `per_run_usd`,
  `daily_usd` (seeded via a temp SQLite DB), and `monthly_usd`; budget
  bypass when `block_over_budget: false`; `record_call()`/`get_spend()`
  round-trip and multi-call summing.
- `tests/test_privacy_guard.py` (12 tests) — `scan_for_secrets()` catches
  Anthropic-style, OpenAI-style, AWS access-key-ID, `KEY=value`, and
  bearer-token shapes, and returns empty for clean text;
  `build_minimal_payload()` proves role-scoping by construction — a fake
  secret and unrelated text placed in an `extra` dict key that role
  doesn't read never appears in the built payload, for judge, synthesizer,
  and an unrecognized role; `guard_payload()` raises `PrivacyGuardError`
  on a tainted payload and returns clean payloads unchanged.

All three test files use either pure policy/privacy/cost logic (no
adapter at all) or `monkeypatch` — never `MockCloudAdapter` was strictly
needed for these particular tests since none of them exercise an actual
adapter `.call()`, but `MockCloudAdapter` now exists in `adapters.py` for
any future test (e.g. a Phase 8 UI test) that needs a fake cloud response
without a real network call.

Confirmed via `grep` across all new files and tests: no `requests.post`,
`requests.get`, `anthropic.`, `httpx`, or `urllib` usage anywhere in the
Phase 7 code or tests — no real network call is possible from this
implementation.

## Tests run

```
ruff check .                                                              → All checks passed!
pytest tests/test_cloud_policy.py tests/test_cost_tracker.py tests/test_privacy_guard.py -v → 33 passed
pytest tests/ -v                                                          → 146 passed
```

## Confirmation of no real network calls

No real network call was made during implementation or testing in this
session. `.env` was never read or edited. No provider credentials were
added. `cloud.enabled` remains `false` in the committed config.
`AnthropicAdapter.call()` still raises `NotImplementedError` and cannot
make a network request even if every other gate is somehow satisfied.

## Files changed

- `config/models.yaml`
- `orchestrator/config_loader.py`
- `orchestrator/adapters.py`
- `orchestrator/database.py`
- `run.py`
- `orchestrator/cloud_policy.py` (new)
- `orchestrator/privacy_guard.py` (new)
- `orchestrator/cost_tracker.py` (new)
- `tests/test_cloud_policy.py` (new)
- `tests/test_cost_tracker.py` (new)
- `tests/test_privacy_guard.py` (new)
- `docs/audits/2026-07-04-phase-7-maintainer-report.md` (new)

## Remaining risks / TODOs

- **Real `AnthropicAdapter.call()` is not implemented.** Before it can be,
  someone must personally verify the current Claude model ID and per-token
  pricing against Anthropic's official published documentation and update
  `config/models.yaml`'s `cloud.model`/`cloud.pricing` accordingly — do
  not copy the current placeholder values into a real call.
- `estimate_cost()`'s pre-call token estimate in `run.py`'s
  `_maybe_escalate_to_cloud()` uses a rough `len(payload) // 4` heuristic
  for both input and (assumed-symmetric) output tokens. This is a
  conservative placeholder for budget-checking purposes only, clearly
  documented as an approximation, not a precise prediction.
- Streamlit display of cloud status/approval/cost is explicitly deferred
  to Phase 8, per the guide — no UI changes were made in this phase.
- The escalation call site is currently wired only at the Synthesizer
  step. Extending it to the Judge step (also allow-listed by default)
  would follow the same pattern if desired later.

## Commit

```
feat: add cloud fallback scaffolding (policy, privacy guard, cost tracker), off by default
```
