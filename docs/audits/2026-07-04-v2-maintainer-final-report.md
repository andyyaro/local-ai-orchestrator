# v2.0 Maintainer Final Report — Phases 7 through 12

## Summary

All six v2.0 phases (7–12) were implemented, tested, and merged into
`main` in sequence, each in its own branch and PR, with CI passing on
every merge. No hard-stop condition was triggered at any point. This
report consolidates the per-phase maintainer reports; see each phase's
own `docs/audits/2026-07-04-phase-N-maintainer-report.md` for full detail.

## Phases completed

| Phase | Title | PR | Squash-merge SHA |
|---|---|---|---|
| 7 | Optional cloud fallback scaffolding | [#12](https://github.com/andyyaro/local-ai-orchestrator/pull/12) | `da48de3` |
| 8 | Streamlit updates | [#13](https://github.com/andyyaro/local-ai-orchestrator/pull/13) | `3654cab` |
| 9 | Retrieval and long-context-equivalent memory | [#14](https://github.com/andyyaro/local-ai-orchestrator/pull/14) | `f7a9fda` |
| 10 | Deep research and internet connection | [#15](https://github.com/andyyaro/local-ai-orchestrator/pull/15) | `b2d3293` |
| 11 | Claude-Code-style coding-agent subsystem | [#16](https://github.com/andyyaro/local-ai-orchestrator/pull/16) | `ad94da5` |
| 12 | Final eval suite and release checklist | [#17](https://github.com/andyyaro/local-ai-orchestrator/pull/17) | `02b7a1b` |

## Phases not completed

None. All six v2.0 phases were attempted and completed; no hard-stop
condition (ruff failure, pytest failure, CI failure, merge failure,
unexpected file changes, credential/paid-call requirement, force-push/
reset/clean requirement, unsandboxable coding-agent risk, or scope
ambiguity) was ever triggered.

## Branch cleanup status

Every phase branch was squash-merged, then had its remote branch deleted
via `gh pr merge --delete-branch`, and its local branch was confirmed
removed (either automatically by the same command, or verified via
`git branch -a` showing no local phase branches remaining and
`git fetch --prune` showing the remote ref deleted). Final state after
Phase 12:

```
git branch -a
* main
  remotes/origin/HEAD -> origin/main
  remotes/origin/main
```

No stale phase branches remain locally or on the remote.

## Files changed by phase

**Phase 7 — Cloud fallback scaffolding**
`config/models.yaml`, `orchestrator/config_loader.py`,
`orchestrator/adapters.py`, `orchestrator/database.py`, `run.py`,
`orchestrator/cloud_policy.py` (new), `orchestrator/privacy_guard.py`
(new), `orchestrator/cost_tracker.py` (new),
`tests/test_cloud_policy.py` (new), `tests/test_cost_tracker.py` (new),
`tests/test_privacy_guard.py` (new).

**Phase 8 — Streamlit updates**
`app/streamlit_app.py` (535 lines removed, duplicated pipeline logic
deleted), `run.py` (added pluggable `on_step` callback),
`tests/test_pipeline_routing.py` (1 new test).

**Phase 9 — Retrieval memory**
`config/models.yaml`, `orchestrator/config_loader.py`,
`orchestrator/database.py`, `orchestrator/graph.py`,
`orchestrator/state.py`, `requirements.txt`, `run.py`, `memory/__init__.py`,
`memory/chunking.py`, `memory/embeddings.py`, `memory/indexer.py`,
`memory/retriever.py` (all new), `tests/test_memory.py` (new).

**Phase 10 — Deep research and internet connection**
`config/models.yaml`, `orchestrator/config_loader.py`,
`requirements.txt`, `research/__init__.py`, `research/search_provider.py`,
`research/fetcher.py`, `research/prompt_injection_guard.py`,
`research/source_registry.py`, `research/citation_verifier.py`,
`research/run_research.py` (all new), `tests/test_citation_verifier.py`,
`tests/test_fetcher.py`, `tests/test_prompt_injection_guard.py`,
`tests/test_search_provider.py` (all new).

**Phase 11 — Coding-agent subsystem**
`coding_agent/__init__.py`, `coding_agent/repo_map.py`,
`coding_agent/patch_tool.py`, `coding_agent/todo_state.py`,
`coding_agent/test_loop.py` (all new), `tests/test_coding_agent.py` (new).
No existing file was modified — this phase was purely additive.

**Phase 12 — Final eval suite**
`eval/__init__.py`, `eval/scenarios.py`, `eval/run_eval_suite.py` (all
new), `tests/test_eval_suite_importable.py` (new). No existing file was
modified.

## Tests run by phase

| Phase | Phase-specific tests | Full suite (`pytest tests/ -v`) |
|---|---|---|
| 7 | 33 passed | 146 passed |
| 8 | 1 new (`on_step` callback) | 147 passed |
| 9 | 13 passed | 160 passed |
| 10 | 22 passed (7 citation + 5 fetcher + 5 injection-guard + 5 search-provider) | 182 passed |
| 11 | 19 passed | 201 passed |
| 12 | 2 passed (import smoke) | 203 passed |

Final test count on `main`: **203 tests, all passing.**

## CI result by phase

`lint-and-test` (the project's single CI workflow) passed on both
required check runs for every one of the six PRs (#12–#17) — no CI
failure occurred at any point across v2.0.

## Final `git status -sb`

```
## main...origin/main
```

Clean. `main` is up to date with `origin/main`, no local or remote phase
branches remain.

## Remaining risks (consolidated across all six phases)

- **Phase 7**: `AnthropicAdapter.call()` is deliberately left
  unimplemented — the model ID and pricing in `config/models.yaml`'s
  `cloud` section were never verified against Anthropic's current
  published documentation in any session. A real cloud call cannot
  happen until that verification is done and the adapter is implemented
  for real.
- **Phase 8**: the cloud cost/approval panel in Streamlit is
  informational-only, not a functioning approve/deny control —
  `cloud_policy.request_human_approval()` blocks on real terminal
  `input()`, which is unsafe to call from a Streamlit background thread.
  A correct implementation needs session-state-based pause/resume
  infrastructure, deferred as a larger follow-up.
- **Phase 9**: `nomic-embed-text` is not pulled locally in this
  environment, so retrieval has never been exercised against real
  project data — only against fake/deterministic embeddings in tests and
  a real-but-gracefully-skipped attempt in Phase 12's eval suite.
  `memory.indexer.index_run()`/`index_project_file()` are not yet wired
  to run automatically anywhere (e.g. at the end of every pipeline run).
- **Phase 10**: `BraveSearchProvider.search()` is deliberately left
  unimplemented for the same reason as Phase 7's adapter — the Brave
  Search API schema was never verified against official docs. A real
  research run today can only use `MockSearchProvider`'s canned results.
  `detect_contradictions()` exists but isn't wired into
  `reject_unverified_citations()`'s enforcement path.
- **Phase 11**: `_default_propose_fix()`'s model-output parsing (a
  `FILE: <path>` line plus one fenced code block) is a simple, single
  format — a model that doesn't follow it raises a clear `ValueError`
  rather than misbehaving, but a more robust parser would help real
  repeated use. The subsystem has no CLI entry point yet; it's a set of
  library functions, matching Phase 10's "narrow, separate" pattern.
- **Phase 12**: **`eval_simple_coding_task` genuinely fails** as of this
  report — reproduced across three separate runs, the Supervisor
  classifies an unambiguous coding goal as `mode="general"` rather than
  `"coding"` using the `serious` profile's default supervisor model
  (`llama3.1:8b`). This is a real, actionable finding, not an eval-suite
  bug (verified by inspecting the raw `00_supervisor.json` output
  directly) — see the Phase 12 report for full detail. It was
  intentionally **not** fixed in Phase 12, since doing so would require
  editing `prompts/supervisor.txt`, outside that phase's explicit scope.

## Known limitations (things that work as designed but are worth knowing)

- Two real providers (`AnthropicAdapter`, `BraveSearchProvider`) are
  scaffolded but not activated anywhere in the shipped system — this is
  intentional, mirroring the same "verify before activating" discipline
  applied consistently across both phases.
- `sqlite-vec` and `beautifulsoup4` were installed into this session's
  `.venv` via `pip install` (both declared in `requirements.txt`) to
  verify Phases 9 and 10's real, non-mocked code paths — a fresh clone
  following the README's existing `pip install -r requirements.txt` step
  will pick these up automatically.
- The eval suite (`eval/run_eval_suite.py`) is explicitly a human-run
  acceptance step, not part of CI — running it takes real wall-clock time
  (10–20+ minutes observed across three runs in this session, driven by
  genuine local-model variance) and should be budgeted for before any
  future merge or release decision, not treated as instant.
- `orchestrator/graph.py` (the LangGraph alternate pipeline) was kept in
  parity with `run.py` throughout every phase that touched pipeline
  behavior (7 to the extent relevant, 9), consistent with the practice
  established in earlier v1.1 phases.

## Whether v2.0 is complete

**Yes**, per this project's own definition of "done" (from
`docs/upgrade-guide/20-final-roadmap.md`): every phase attempted has its
own merged branch, its own passing tests, its own entry in `git log`, and
this consolidated report. All six v2.0 phases (7–12) are merged and
stable. The roadmap explicitly frames "possible," not "required" — this
is a complete v2.0 upgrade in the sense the roadmap itself defines.

## Whether a release/tag is ready for human approval

**Not yet, pending human review of the remaining risks above.** No git
tag or GitHub Release was created in this session (as instructed), and
none should be created without a human explicitly deciding to do so.
Specifically, before considering a release:

1. A human should decide whether the `eval_simple_coding_task` finding
   (Supervisor coding-mode misclassification) needs a fix before release,
   or is acceptable to ship with, documented as a known issue.
2. If cloud fallback (Phase 7) or real web search (Phase 10) matter for
   the intended release, their real provider integrations need to be
   personally verified and implemented — both are currently deliberately
   inert stubs.
3. A live `streamlit run app/streamlit_app.py` check and a
   `bash scripts/local_acceptance.sh` run should be performed by a human
   with normal (non-sandboxed) network/port access — both were verified
   in their original phases (8, and 6b/6c respectively) but not re-run in
   this final v2.0 pass, since no pipeline behavior changed since then.
4. All of the above are judgment calls appropriate for the maintainer,
   not something this session should decide unilaterally.

This session's work is complete through Phase 12 as scoped. No new work
was started beyond Phase 12.
