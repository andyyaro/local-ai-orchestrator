# 20 — Final Roadmap

## The full phase list, in order

```text
v1.1 (do these first, in order):
  Phase 0 — Repo audit and safety baseline
  Phase 1 — CI foundation
  Phase 2 — Deterministic validators
  Phase 3 — Routing, speed, and pipeline collapse
  Phase 4 — Timeout and resilience
  Phase 5 — Metrics and profiling
  Phase 6 — MacBook memory discipline

v2.0 (only after v1.1 is merged and stable):
  Phase 7  — Optional cloud fallback scaffolding
  Phase 8  — Streamlit updates
  Phase 9  — Retrieval and long-context-equivalent memory
  Phase 10 — Deep research and internet connection
  Phase 11 — Claude-Code-style coding-agent subsystem
  Phase 12 — Final eval suite and release checklist
```

## Why this order, specifically

Phases 0–6 are ordered by dependency, not just priority:

- **Phase 0** must come first because every later phase's "files to inspect"
  list assumes you already know whether `run.py` and `orchestrator/graph.py`
  have diverged.
- **Phase 1** comes second because every phase from here on wants an
  automatic pass/fail signal on push — building it late means Phases 2–6
  ran without a safety net for no good reason.
- **Phase 2** comes before Phase 3 because routing changes how many times
  the Judge and validators run per goal — you want validators already
  proven correct before you start changing call counts around them.
- **Phase 4** comes after Phase 3 because resilience logic (timeout budgets,
  fallback models) is easier to reason about once you know which paths
  (fast/normal/deep) actually make which calls.
- **Phase 5** comes after Phases 3 and 4 deliberately — metrics are most
  useful once there's routing and resilience data worth collecting; it can
  technically run standalone, but you'd only be aggregating per-agent
  timing with nothing to compare it against.
- **Phase 6** comes last in v1.1 because it directly builds on Phase 5's
  `calls_by_model` field to prove the model-swap fix actually worked, not
  just assert that it should.

Within v2.0:

- **Phase 7** is first because Phase 8 (Streamlit) needs something to
  display, and later phases (9, 10) don't depend on it at all — you could
  reorder 7 after 9/10 if cloud fallback matters less to you than retrieval
  or research. This is the one place in the roadmap where reordering is
  genuinely safe.
- **Phase 8** comes right after 7 specifically because of the finding in
  that phase file: `app/streamlit_app.py` has its own third pipeline
  implementation, and the longer that sits unfixed, the more phases'
  worth of logic have to be back-ported into it later.
- **Phase 9 and 10** are independent of each other and can be reordered
  freely based on which matters more to you — retrieval (9) is lower-risk
  (no internet access) and arguably a better next step than research (10)
  if you want to build confidence before adding a network boundary.
- **Phase 11** is placed last among the feature phases because it's the
  highest-risk phase in the guide (a model editing real files in a loop) —
  do it once everything else is solid and you have a clear sense of how
  this project's guardrail patterns (boundary checks, human gates, minimal
  payloads) actually hold up in practice.
- **Phase 12** is last by definition — it evaluates whatever you've actually
  built, and its scenarios are designed to skip gracefully for anything not
  yet implemented, so it's genuinely safe to run after *any* phase, not
  only at the very end.

## Decision points — where you can legitimately stop or skip

- **After Phase 6:** this is a complete, coherent stopping point. The two
  original problems (ignored constraint, 12m49s runtime) are fixed, CI
  exists, and you have real metrics. Stopping here and living with a
  v1.1-only system is a completely reasonable outcome, not an unfinished
  one.
- **Skip Phase 7 entirely** if you never want this project to make an
  external network call under any circumstance. Nothing in Phases 8–12
  strictly requires Phase 7 (Phase 8's cloud panel just won't have anything
  to show).
- **Skip Phase 10** if deep research isn't a goal for this project — Phase
  9 (retrieval over your own run history and project files) is independent
  and useful on its own.
- **Skip Phase 11** if you don't want a second, self-modifying coding
  agent living inside a project you already edit with Claude Code — this
  is the most speculative, "portfolio/research interest" phase in the
  whole guide, not a core need.
- **Always do Phase 12** last, regardless of how many other v2.0 phases you
  chose — it's cheap (mostly a script), and it's what turns "I think this
  works" into "I checked this works."

## What "done" looks like for this whole upgrade

Not "all 12 phases implemented." Done means: every phase you *did* implement
has its own merged branch, its own passing tests, its own entry in
`git log`, and passed the Phase 12 eval suite and final checklist before
merging. A project with Phases 0–6 merged cleanly and Phases 7–11 never
started is a fully "done" v1.1 upgrade — the roadmap describes what's
*possible*, not what's *required*.
