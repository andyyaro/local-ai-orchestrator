# 18 — Troubleshooting

This is a symptom-first index across every phase in this guide. Each entry
names the likely cause and points to the phase file with the full fix — this
page intentionally doesn't repeat the detailed "If it fails" sections
already in each phase file (`05` through `17`).

## "Ruff or pytest fail right after I checked out a phase branch"

**Likely cause:** the branch was created from a `main` that itself wasn't
clean, or a previous phase's branch was never actually merged.

**Fix:** run `git log --oneline --graph --all` to see whether your current
branch's parent commit is really `main`'s tip. If not, you likely branched
from an old or abandoned phase branch by mistake. See
`01-safety-and-branching.md` section 1.1–1.2.

## "GitHub Actions shows red but the same commands pass locally"

**Likely cause:** a dependency version difference between your Mac and the
Linux runner, or a file that exists locally but was never committed (check
`.gitignore` isn't accidentally excluding something `ci.yml` needs).

**Fix:** read the exact Actions log error, don't guess. See
`03-github-actions-ci.md` section 3.6 and `06-phase-1-ci-foundation.md`'s
"If it fails" section.

## "The self-hosted runner did something I didn't expect"

**Stop the runner process immediately.** Then see
`04-self-hosted-macbook-runner.md` section 4.8 for the disable/rollback
steps. Re-read section 4.4's hard rules before re-enabling anything —
this is the single highest-blast-radius piece of infrastructure in the
whole guide.

## "A run passed even though the output ignores an explicit constraint (word count, format, etc.)"

**Likely cause:** either Phase 2 hasn't been implemented yet, or
`orchestrator/validators.py`'s constraint-extraction regex doesn't recognize
the specific phrasing the goal used.

**Fix:** see `07-phase-2-validators.md`. Add the exact goal phrasing as a new
regression test in `tests/test_validators.py` before touching the regex.

## "Runs still take a very long time even after Phase 3 and Phase 6"

**Likely cause:** check `run_summary.json`'s `metrics.calls_by_model` (Phase
5) first — if it shows more than one distinct 14B-class model name, Phase
6's profile consolidation either wasn't applied to the profile you're
actually using, or a CLI override (`--model-main`/`--model-fast`) is
reintroducing a second large model for one run.

**Fix:** see `11-phase-6-memory-discipline.md`. Run
`pytest tests/test_model_config.py -v` — it should fail loudly if a profile
ever mixes two 14B-class models again.

## "A model call hangs or times out and the whole process seems stuck"

**Likely cause:** Phase 4 hasn't landed yet (so the old blind-retry
`time.sleep(3)` loop in `agents/base_agent.py` is still in place), or the
per-model timeout budget in Phase 4's config is set too high for the model
actually being called.

**Fix:** see `09-phase-4-timeout-resilience.md`. Confirm
`get_timeout_for_model()` is actually threaded into the real HTTP call's
`timeout=` argument, not just computed and discarded.

## "The pipeline crashed with a raw Python traceback instead of a clean message"

**Likely cause:** Phase 4's `FatalModelError` isn't being caught in
`run.py`'s `main()`, or a new exception type was introduced somewhere that
isn't a subclass of `ModelCallError`.

**Fix:** see `09-phase-4-timeout-resilience.md` step 6.

## "A cloud call happened when I didn't expect one"

**Treat this as a real incident, not a minor bug.** Immediately check
`config/models.yaml`'s `cloud.enabled` value and confirm whether
`--allow-cloud` was passed. Check the `cloud_calls` SQLite table for the
exact row (timestamp, role, model, cost) to understand what happened.

**Fix:** see `12-phase-7-cloud-fallback.md` — recall that a real cloud call
requires **five independent conditions** to all hold; if one happened
unexpectedly, one of those five checks has a bug, and that's the priority
fix before doing anything else.

## "Streamlit shows 'Local only' but cloud fallback is actually enabled"

**Likely cause:** Phase 8 wasn't implemented, or its status pill still uses
the old hardcoded `render_status_pill("Local only", "green")` call instead
of reading `cloud_policy.is_cloud_enabled()`.

**Fix:** see `13-phase-8-streamlit-updates.md` step 4 — this is called out
specifically because a wrong status indicator is worse than no indicator.

## "Retrieval returns irrelevant or no results"

**Likely cause:** the embedding model (`nomic-embed-text` by default) isn't
pulled, or `hybrid_search`'s score-merging weights one signal too heavily.

**Fix:** see `14-phase-9-retrieval-memory.md`'s "If it fails" section.
Confirm with `ollama list` before assuming the code is broken.

## "A generated research report cites something that isn't real"

**This is exactly the failure mode Phase 10 exists to catch.** If it's
happening after Phase 10 landed, `citation_verifier.py`'s
`reject_unverified_citations` should have flagged it — check whether the
report you're looking at actually went through that function, or was shown
to you before verification ran.

**Fix:** see `15-phase-10-deep-research.md`.

## "The coding agent changed a file I didn't expect, or touched this repo itself"

**Stop and treat this as critical.** Check `git status --short` in whatever
`target_root` you pointed the coding agent at — and separately, in this
orchestrator repo itself, to confirm nothing here was touched.

**Fix:** see `16-phase-11-coding-agent.md`'s safety warning and "If it
fails" section — this should never happen if `allow_self_repo` defaults to
`False` and the path-boundary check in `propose_change()` is correct.

## "I don't know if my branch is actually ready to merge"

Run the Phase 12 eval suite and the final checklist:

```bash
python eval/run_eval_suite.py
```

See `17-phase-12-eval-suite-checklist.md` for the full checklist.

## "I'm not sure which phase caused a regression"

This is exactly why phases live on separate branches with separate commits
— see `19-rollback-guide.md` for how to isolate and revert a single phase
without undoing others.
