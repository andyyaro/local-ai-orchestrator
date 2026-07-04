# 00 — Overview and Upgrade Philosophy

## 0.1 What this guide is for

You already have a working system. Local AI Orchestrator v1.0.0 runs a 7-agent pipeline locally on your MacBook, saves run history to SQLite, verifies code execution, and passes its own tests. That is a real, working foundation — this guide does not throw any of it away.

Two concrete problems triggered this upgrade:

1. A smoke test passed even though the output ignored a 120-word limit.
2. A full run took 12 minutes 49 seconds.

Both problems come from **architecture gaps, not hardware limits**. Your MacBook Pro (M3, 24GB) is not the bottleneck. The bottleneck is that (a) nothing in the code checks a word count deterministically, and (b) the pipeline swaps between multiple different 14B-class models in a single run, and each swap costs real load time on top of already-slow decode speed. This matters because it changes what you should fix first: not "get a bigger machine," but "add code-level checks and stop swapping models."

## 0.2 What "upgrade" means here

This guide walks you from v1.0.0 toward v1.1 and, eventually, v2.0. It is organized as **13 phases** (Phase 0 through Phase 12). Each phase is small enough to implement, test, and verify in one sitting. You are not meant to implement all of them this week, or even this month. Some phases (validators, CI, routing) are immediately worth doing. Others (deep research, coding-agent subsystem) are advanced, optional, and should only be attempted after the earlier phases are solid.

**v1.1 scope** (do these first, in order): Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6. These fix the two known weaknesses (constraint failures, slow runtime) and give you the safety net (CI, metrics) to make every later change measurable.

**v2.0 scope** (only after v1.1 is stable and merged): Phase 7 → Phase 8 → Phase 9 → Phase 10 → Phase 11 → Phase 12. These add optional cloud fallback, retrieval memory, deep research, and a coding-agent subsystem — all bigger, riskier, and more speculative.

Do not skip ahead. A validator built on top of an un-metered, un-tested pipeline is a validator you can't verify actually helped.

## 0.3 Why staged implementation matters specifically for you

You're using Claude Code as your implementation agent, which means it's tempting to say "implement the whole v2.0 architecture" in one prompt. Don't do that, for three concrete reasons:

- **You can't verify a giant diff.** If Claude Code changes 30 files in one pass and something breaks, you won't know whether it was the validator, the router, or the cloud policy. A single-phase diff is small enough to read in five minutes.
- **Rollback needs a clean boundary.** If Phase 3 (routing) turns out to be a bad idea, you want to `git reset` to the commit right before Phase 3 started — not untangle it from Phase 4's timeout logic that was implemented in the same sweep.
- **CI needs something stable to check against.** Phase 1 sets up GitHub Actions specifically so that every later phase has an automatic pass/fail signal. That signal is meaningless if five phases land in one commit.

The staged workflow, in full, is:

```text
plan → branch → implement one phase → run tests → verify locally → commit → move to next phase
```

You will repeat this loop 13 times (once per phase), not once for the whole project.

## 0.4 The three tracks

This guide sets up three tracks that work together but do different jobs:

**Track A — GitHub Actions CI (`ci.yml`).** Runs on GitHub-hosted Linux runners, on every push and PR. It checks Ruff and pytest, using mocked adapters — no real Ollama, no real 14B models, no GPU, no cloud calls. It is fast (~1–2 minutes) and catches syntax errors, broken imports, failed unit tests, and lint violations. It is a **checker**, not an implementer. It cannot tell you whether the real pipeline runs correctly on your actual Mac.

**Track B — Self-hosted MacBook runner (`macbook-acceptance.yml`, optional).** Runs on your own Mac, triggered manually. It can start Ollama, pull/verify small models, run a real end-to-end pipeline smoke test, and check real runtime against a threshold. This is the only track that tests your actual hardware and actual models. It is optional, manual-trigger-only, and never runs on untrusted pull requests (explained fully in the CI/runner chunk).

**Track C — Claude Code implementation workflow.** This is how changes get written in the first place: you give Claude Code a scoped, single-phase prompt from this guide, it edits files, runs tests locally, and reports back — but it does not merge, tag, or enable cloud calls on its own.

Together: **Claude Code implements → Track A checks automatically → Track B optionally verifies on real hardware → you review the diff → you merge.** GitHub-hosted runners do not perfectly mimic your M3 24GB machine (different CPU architecture assumptions aside, they simply don't have your Ollama models or your memory profile), so Track A passing does not mean "this works on my Mac." Track B is what actually confirms that. Never treat a green Track A run as permission to skip using the app yourself.

## 0.5 What this guide will not tell you to do

Explicitly out of scope, and actively discouraged, for reasons explained in each relevant phase:

- Trying to get true 1-million-token local context. The KV cache math doesn't fit in 24GB of unified memory — retrieval is the realistic substitute (Phase 9).
- Fine-tuning large (14B+) models locally as a first move.
- Auto-downloading models. Every model pull remains something you type yourself.
- Enabling cloud calls by default. Cloud fallback (Phase 7) is opt-in, per-role, and budget-limited.
- Blind exponential backoff for local Ollama timeouts — that pattern is designed for shared-server rate limits, not a single local model that's just slow (Phase 4 explains why).
- Running 14B/30B model tests on GitHub-hosted runners — they don't have the models or the memory, and pretending otherwise wastes CI minutes for a result that tells you nothing.
- Auto-merging to `main` or auto-tagging releases. Every merge and every release stays a manual, explicit action you take.
- Rewriting the pipeline from scratch. `run.py` and `orchestrator/graph.py` both work today; every phase in this guide extends them.

## 0.6 Known repo quirks this guide accounts for

A few things found during repo inspection that shape how later phases are written:

- There are **two parallel pipeline implementations**: the plain `run.py` entry point and the LangGraph version in `orchestrator/graph.py` (run via `run_langgraph.py`). Any change to pipeline behavior (validators, routing, timeouts, metrics) needs to be checked against both, or explicitly scoped to one with a note explaining why the other wasn't touched.
- `docs/research/README.md` references report filenames that don't match what's actually on disk. The real files are `docs/research/compass_artifact_wf-f11fd32d-aa8a-4145-ba84-db3f3fd5d412_text_markdown.md` (cloud fallback report) and `docs/research/compass_artifact_wf-f402f792-b685-4b93-a2ec-97ba81ce8d8e_text_markdown.md` (v1→v2 architecture report). This guide uses the real filenames.
- `orchestrator/adapters.py` already has a clean `ModelAdapter` interface with working `OllamaAdapter`, plus `OpenAIAdapter`/`AnthropicAdapter` stubs that just raise `NotImplementedError`. Phase 7 builds on this interface rather than replacing it.
- `orchestrator/logger.py` already emits structured JSON events (`agent_start`, `agent_end` with `elapsed_ms`, `score`, `code_verification`, `run_stop`, `error`). Phase 5 aggregates these into `run_summary.json` rather than building a new logging system.
- `orchestrator/database.py` only has `runs` and `iterations` tables today. Phase 7's cloud-call audit trail needs a schema addition (`cloud_calls` table), not a new database.
- `orchestrator/code_runner.py` already blocks dangerous patterns (`eval`, `exec`, `os.system`, network calls, etc.) and runs generated code in a subprocess with a timeout. Phase 11's coding-agent subsystem extends this rather than rebuilding sandboxing from scratch.
