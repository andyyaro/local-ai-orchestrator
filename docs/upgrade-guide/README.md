# Local AI Orchestrator — v1.1/v2 Upgrade Guide

This folder is the implementation guide for upgrading Local AI Orchestrator from
v1.0.0 toward v1.1 and, later, v2.0. It is based on the current repo state plus
the two research reports in `docs/research/`.

All 21 sections below are written. This guide describes what to build — it
does not implement any of it. No phase has been started yet.

Do not implement any phase until you have read `00-overview.md`,
`01-safety-and-branching.md`, and `02-claude-code-workflow.md` first.

## Guide index

- [00 — Overview and upgrade philosophy](00-overview.md) — **(written)**
- [01 — Safety rules and branch strategy](01-safety-and-branching.md) — **(written)**
- [02 — How to use Claude Code for this upgrade](02-claude-code-workflow.md) — **(written)**
- [03 — GitHub Actions CI foundation (`ci.yml`)](03-github-actions-ci.md) — **(written)**
- [04 — Optional self-hosted MacBook runner (`macbook-acceptance.yml`)](04-self-hosted-macbook-runner.md) — **(written)**
- [05 — Phase 0: Repo audit and safety baseline](05-phase-0-repo-audit.md) — **(written)**
- [06 — Phase 1: CI foundation](06-phase-1-ci-foundation.md) — **(written)**
- [07 — Phase 2: Deterministic validators](07-phase-2-validators.md) — **(written)**
- [08 — Phase 3: Routing, speed, and pipeline collapse](08-phase-3-routing-speed.md) — **(written)**
- [09 — Phase 4: Timeout and resilience](09-phase-4-timeout-resilience.md) — **(written)**
- [10 — Phase 5: Metrics and profiling](10-phase-5-metrics.md) — **(written)**
- [11 — Phase 6: MacBook memory discipline](11-phase-6-memory-discipline.md) — **(written)**
- [12 — Phase 7: Optional cloud fallback scaffolding](12-phase-7-cloud-fallback.md) — **(written)**
- [13 — Phase 8: Streamlit updates](13-phase-8-streamlit-updates.md) — **(written)**
- [14 — Phase 9: Retrieval and long-context-equivalent memory](14-phase-9-retrieval-memory.md) — **(written)**
- [15 — Phase 10: Deep research and internet connection](15-phase-10-deep-research.md) — **(written)**
- [16 — Phase 11: Claude-Code-style coding-agent subsystem](16-phase-11-coding-agent.md) — **(written)**
- [17 — Phase 12: Final eval suite and release checklist](17-phase-12-eval-suite-checklist.md) — **(written)**
- [18 — Troubleshooting](18-troubleshooting.md) — **(written)**
- [19 — Rollback guide](19-rollback-guide.md) — **(written)**
- [20 — Final roadmap (v1.1 vs. v2 split)](20-final-roadmap.md) — **(written)**

## Scope reminder

- **v1.1 scope**: Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6.
- **v2.0 scope**: Phase 7 → Phase 8 → Phase 9 → Phase 10 → Phase 11 → Phase 12.

Do not implement all phases at once. Each phase gets its own branch, its own
tests, its own verification step, and its own commit — see
`01-safety-and-branching.md` for the full workflow.
