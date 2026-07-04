# Local AI Orchestrator: Cloud Fallback Architecture & the Realistic Path to Sonnet 5-Level Workflow Quality (Follow-Up Report v2.1)

## 1. Executive summary

Optional cloud fallback for Local AI Orchestrator should be designed as an **off-by-default, per-role, per-trigger, human-gated escalation layer** that sends the *smallest possible sanitized payload* — most often the Judge step or the final Synthesizer step, not the whole task — to a single frontier model (Claude Sonnet 5 is the best-fit default), with deterministic cost and secret-scanning guards in front of every external call. This is the single most defensible way for a 24 GB M3 MacBook to approach "Sonnet 5-level" *workflow* output without pretending a local model has become a frontier model.

Sonnet 5 is a real, current Anthropic model. Per Anthropic's launch post "Introducing Claude Sonnet 5" (June 30, 2026), it is priced at "$2 per million input tokens and $10 per million output tokens through August 31, 2026, after which it will be priced at $3 per million input tokens and $15 per million output tokens"; the model ID is `claude-sonnet-5`, with a 1M-token context window and 128K max output, and it is positioned as "the most agentic Sonnet yet" and a drop-in replacement for Sonnet 4.6. Because Anthropic publishes only limited head-to-head benchmarks for it, we anchor "Sonnet 5-level" to a small set of measurable proxies (SWE-bench-style coding, strict-constraint compliance, citation reliability, long-horizon completion) and distinguish four different things the phrase could mean: model quality, workflow quality, agent-system quality, and product quality. Local Orchestrator cannot match Sonnet 5's raw single-model quality, but on *narrow, verifiable task classes* (constraint-checked writing, test-passing single-file code, citation-verified research) a verifier-guided local-first loop with optional cloud fallback can reach practical parity.

The previous report was directionally correct — the bottlenecks are architectural, not hardware, and cloud fallback is the realistic path to frontier-level workflow quality — but it left the entire fallback design (routing, privacy, cost, implementation, evaluation) unspecified, and it repeated the README's claim that "OpenAI and Anthropic stubs exist" without noting that the repo's own roadmap still lists provider support as an open TODO, meaning those stubs are almost certainly minimal placeholders rather than working adapters.

## 2. What the previous report did not fully answer

The v1.0.0→v2.0 report established the right conclusions (architecture-limited, not hardware-limited; MacBook sufficient for a portfolio-grade local-first orchestrator; cloud fallback the plausible path to frontier quality) but under-specified six things this follow-up resolves:

1. **How fallback is actually designed** — modes, what leaves the machine, defaults, consent.
2. **Which cloud model to use and why** — with primary-source specs/pricing, chosen on fit not popularity.
3. **Which of the seven agent roles benefit** — and what to send for each.
4. **Triggering/routing logic** — a concrete policy matrix, automatic vs. approval-gated.
5. **Privacy, security, cost governance** — redaction, secret-scanning, budgets, audit trail.
6. **Concrete repo-level implementation and evaluation** — files to add/change, tests, and a benchmark that proves fallback was worth it.

## 3. Repo verification findings (grounded in actual inspection)

I directly fetched and read the repository's `README.md` and `run.py`. I attempted to fetch `orchestrator/adapters.py`, `config/models.yaml`, and `orchestrator/database.py` directly and via a dedicated sub-agent; those raw files could not be retrieved (the repo is brand-new with zero stars and is not yet indexed, and raw/blob fetches were blocked). The following are therefore split into **verified** and **unverified-but-documented**.

**Verified from `run.py` (488 lines):**
- The 7-agent serial pipeline is real and matches the description: `SupervisorAgent → PlannerAgent → BuilderAgent → [Critic → Fixer → (code verify) → Judge] loop → SynthesizerAgent`. Agents are imported from `agents/` and the orchestration lives in `run_pipeline()`.
- **Config-driven model routing is real**: `get_model_for_role(role, mode)` and `get_active_profile()` are imported from `orchestrator.config_loader`; CLI flags `--model-main` (Builder/Fixer/Judge/Synthesizer) and `--model-fast` (Supervisor/Planner/Critic) override per-role models via `_role_model()`.
- **Deterministic code verification with hard-fail override is real**: `verify_draft_code()` / `verification_failed()` from `orchestrator.code_runner`; `_apply_code_verification_to_verdict()` forces `pass=False`, `total_score=0`, and appends a `broken_code` hard-fail so a high Judge score cannot rescue broken code.
- **Structured JSON logging is real**: `get_logger()` emits `run_start`, `agent_start`, `agent_end`, `score`, `code_verification`, `stop`, `error` events.
- **SQLite persistence is real**: `save_run(...)` and `init_db()` from `orchestrator.database`; per-run artifacts written to `runs/<timestamp>/` including `run_summary.json`, `best_draft.txt`, `final_output.txt`, `loopNN_*.{txt,json}`.
- Stop conditions: pass-threshold, stall (`min_improvement`), hard-fail, max-loops — all present.

**Verified from `README.md`:**
- Feature bullet: *"Provider-ready adapter layer: Ollama is the default; OpenAI and Anthropic stubs exist for future expansion."*
- Planned Improvements includes an **unchecked** item: *"Add optional OpenAI or Anthropic provider support through config"* and *"Add RAG over previous runs or local documents."*
- Profiles documented: `bootstrap`, `fast`, `serious`, `coding`, selected by `active_profile:`; modes: Writing, Coding, Planning, Debugging, Study, General; `config/modes.yaml` exists.
- The repo also contains `run_langgraph.py`, `run_phase2.py`, `run_phase3.py` (not in the follow-up's stated file list) — evidence the project has already experimented with a LangGraph execution path and phased runners.
- Safety notes already state ".env, .venv/, runs/, logs/ are ignored by Git" and "No data is sent to paid APIs by default."

**Unverified but strongly implied (could not read source):** the exact class layout of `adapters.py` (whether a base adapter class and named `OpenAIAdapter`/`AnthropicAdapter` classes literally exist, even as `NotImplementedError` stubs); the exact per-profile keys in `models.yaml` and whether any provider/cloud field already exists; the exact SQLite schema (table/column names) in `database.py`. The follow-up's file list also references `agents/base_agent.py` and `orchestrator/state.py` — the README file tree confirms `config_loader.py` and a `tests/` directory but does **not** list `base_agent.py` or `state.py`, so those specific files are unconfirmed.

## 4. Prior-report claims to correct, confirm, or revisit

| Prior claim | Verdict | Basis |
|---|---|---|
| Pipeline is 7 serial agents + deterministic verifier | **Confirmed** | Read `run.py` directly |
| Config-driven model routing (YAML) | **Confirmed** | `config_loader` calls in `run.py`; profiles in README |
| SQLite run history + structured JSON logging | **Confirmed** | `save_run`, `get_logger` events in `run.py` |
| Code verifier can hard-fail over the Judge | **Confirmed** | `_apply_code_verification_to_verdict` forces `broken_code` |
| "OpenAI and Anthropic stubs exist" | **Revisit / soften** | README states it, but the roadmap still has an open "add provider support through config" item; stubs are likely placeholders, not working adapters. Treat as *scaffolding intent*, not a functional cloud path. |
| "24 GB MacBook cannot do true 1M-token local context or frontier quality alone" | **Confirmed** | Sonnet 5's 1M window is a server-side feature; local 14B models on 24 GB unified memory are realistically limited to tens of thousands of tokens with heavy quantization |
| "Cloud fallback is the realistic path to frontier-level workflow quality" | **Confirmed, with nuance** | True for verifiable task classes; overstated for open-ended reasoning where a single Sonnet 5 call still wins |
| Known weakness: smoke test ignored a 120-word constraint, ~12m49s | **Confirmed as architectural** | Constraint compliance is a deterministic-validator gap, not a hardware gap; the fix is a word-count validator in the loop, not more RAM |

The 12m49s runtime is worth flagging: on a 24 GB M3, running four sequential 14B-class Ollama models per loop is inherently slow, so any cloud fallback design must treat *latency budget* as a first-class trigger and consider using a smaller/faster local default with cloud escalation only when needed.

## 5. Optional cloud fallback: definitions and modes

Define six explicit modes, selectable in config, with `local-first` (fallback disabled by default within it) as the recommended default install state and `fully-local` as the privacy-max state:

| Mode | What leaves the machine | Which roles may call cloud | Consent | Default? |
|---|---|---|---|---|
| **fully-local** | Nothing, ever | None | N/A | Privacy-max option |
| **local-first (fallback OFF)** | Nothing until user enables a trigger | None until enabled | Cloud disabled by config flag | **Recommended default** |
| **cloud-fallback** | Sanitized payload for the *specific* escalated step only | Judge and/or Synthesizer by default | Per-call or per-session approval | Opt-in |
| **cloud-assist** | Sanitized payload for hard sub-steps (e.g., Builder/Fixer on failing code) | Builder/Fixer/Planner when triggered | Per-session approval + budget cap | Opt-in |
| **frontier/deep** | Larger context (compressed state) for a hard reasoning/research step | Any single role, one call | Explicit per-run confirmation | Opt-in |
| **cloud-only** | Whole task | All | Explicit; defeats the project's premise | **Discouraged** |

**What to actually send on fallback (ranked from safest to riskiest):** (1) compressed local summary of the draft + rubric; (2) Judge-only payload (draft + scoring schema); (3) final synthesis payload (best draft + goal); (4) hardest reasoning sub-question only; (5) retrieved context snippets; (6) sanitized full state; (7) whole raw state (avoid by default). The controller — plain Python, not an LLM — decides which tier applies. Fallback must **never** default to "send the whole task to the cloud."

## 6. Cloud provider/model comparison

Primary-source specs (July 2026). Prices are per **million** tokens (input/output).

| Model | Input/Output | Context | Notable | Fit for this orchestrator |
|---|---|---|---|---|
| **Claude Sonnet 5** | $2/$10 intro → $3/$15 (from Sep 1, 2026) | 1M | Most agentic Sonnet; 128K output; tool use, JSON schema, prompt caching, web search, context awareness; drop-in for Sonnet 4.6; effort parameter | **Best default.** Strong instruction-following + coding + agentic completion; ZDR-eligible on Messages/Token-Counting APIs |
| **Claude Opus 4.8** | $5/$25 | 1M | Highest Anthropic accuracy; agentic-coding leader | Reserve for the *hardest* escalations only (cost 2.5× Sonnet 5) |
| **Gemini 3.1 Pro** | $2/$12 (≤200K), $4/$18 above | up to 2M | Largest context; strong reasoning | Best when *long context* is the bottleneck; cross-family Judge |
| **OpenAI GPT-5.4** | $2.50/$15 | large | Broad ecosystem; strong tools | Viable alternate Judge/Builder; slightly pricier output |
| **DeepSeek V3.2** | ~$0.23/$0.34 | ~164K | Cheapest serious option; sparse attention (DSA) | Best cost/quality for high-volume Judge; **but Chinese provider with no ZDR offering — avoid for sensitive local content** |
| **Mistral (Devstral/large)** | low | mid | Open-weight lineage; EU provider | Good EU-privacy alternative; strong for coding |

**Recommendation:** default single provider = **Claude Sonnet 5** (best agentic completion + instruction-following at Sonnet price, mature JSON-schema/tool support, strong prompt-injection resistance, and a documented short API retention with ZDR available). Offer **Gemini 3.1 Pro** as the long-context option and **DeepSeek V3.2** as an explicit "cheap mode" the user must opt into with a data-sensitivity warning. Do not hard-wire one provider; route through the existing adapter layer.

Note on Sonnet 5 tokenizer: per Anthropic's launch post, "the same input can map to more tokens: roughly 1.0–1.35× depending on the content type" (Anthropic docs describe roughly 30% more tokens than Sonnet 4.6 for the same input). Pre-call cost estimates must therefore use Anthropic's own token counter, not a generic estimate.

## 7. Cloud fallback routing architecture (roles + triggers)

**Per-role recommendation:**

| Role | Stay local by default? | Ever cloud? | Condition | What to send | Expected gain | Metric to prove it |
|---|---|---|---|---|---|---|
| **Supervisor** | Yes | Rarely | Ambiguous goal classification | Goal text only | Low | Mode-classification accuracy |
| **Planner** | Yes | Long-horizon/complex plans | Task classified "deep" | Refined goal + constraints | Medium | Plan completeness score |
| **Builder** | Yes | Hard multi-file coding | Local code fails tests N× | Spec + failing tests | High on hard code | pass@1 after escalation |
| **Critic** | Yes | No | — | — | Low | — |
| **Fixer** | Yes | Repeated repair failure | Tests still fail after repairs | Diff + error trace | High | Test-pass recovery rate |
| **Judge** | Yes | **Best single fallback** | Low/uncertain local score, or cross-check | Draft + rubric schema | High (calibration) | Judge–human agreement |
| **Synthesizer** | Yes | **Best single fallback** | User wants "frontier quality" final | Best draft + goal | High (polish) | Human preference win-rate |
| **Code verifier** | **Always local/deterministic** | **Never** | — | — | N/A | Deterministic pass/fail |

**Cloud Judge vs local Judge:** the strongest, cheapest win. Local LLM-as-judge suffers documented self-preference bias — Wataoka et al., "Self-Preference Bias in LLM-as-a-Judge" (arXiv:2410.21819), show LLM evaluators overestimate their own outputs, and NeurIPS 2024 work links self-recognition ability to self-preference strength — plus position and verbosity biases. A cross-family cloud Judge (e.g., a Claude draft judged by Gemini, or vice-versa) reduces self-preference bias and better calibrates the score that drives the whole improvement loop. **Cloud Synthesizer** is the second-best win: one final polish call materially lifts perceived output quality at one-call cost. **Cloud Builder/Fixer** helps most on genuinely hard coding but is the riskiest for cost and code exfiltration. The deterministic verifier must always stay local — it is code, not a model.

## 8. Fallback POLICY MATRIX (triggers)

| Trigger | Include? | Auto or approval | Configurable | Data sent | Logged / in `run_summary.json` |
|---|---|---|---|---|---|
| Local model timeout | Yes | Approval | Yes | Current step payload | `fallback_events[]` w/ reason=timeout |
| Low local Judge score | Yes | Approval (auto if budget set) | Yes | Draft+rubric | reason=low_score, from/to model |
| Deterministic constraint fail after repairs | Yes | Approval | Yes | Draft+constraint | reason=constraint_fail |
| User selects "frontier quality" | Yes | Explicit (is the consent) | Yes | Best draft | reason=user_frontier |
| Task classified deep/hard | Yes | Approval | Yes | Compressed state | reason=hard_task |
| Coding tests fail repeatedly | Yes | Approval | Yes | Spec+failing tests | reason=tests_fail |
| Citation verification fails | Yes | Approval | Yes | Claims+sources | reason=citation_fail |
| Context too large for local | Yes | Approval | Yes | Compressed summary | reason=context_overflow |
| User explicitly requests cloud | Yes | Explicit | Yes | Per policy tier | reason=explicit |
| Local model unavailable | Yes | Approval | Yes | Current payload | reason=local_unavailable |
| Memory pressure / OOM | Yes | Approval | Yes | Compressed | reason=mem_pressure |
| Latency budget exceeded | Yes | Approval | Yes | Current payload | reason=latency |
| Confidence too low | Yes | Approval | Yes | Draft | reason=low_confidence |

Every fallback writes a structured record (reason, role, provider, model, tokens_sent, est_cost, actual_cost, approved_by, timestamp) into both the JSON log and `run_summary.json`, and surfaces a banner in Streamlit. No trigger fires automatically unless the user has set an explicit per-run budget *and* toggled auto-approve.

## 9. Privacy, security, and cost-control design

**Governance rules (default posture):**
- **Cloud disabled by default.** The privacy promise ("no data sent to paid APIs by default") is already in the README; keep it literally true by shipping `cloud.enabled: false`.
- **Never send by default:** contents of `.env`, secrets/keys/tokens, full repository/file trees, run-history database, anything a secret-scanner flags, PII.
- **Requires explicit confirmation:** any file content, full pipeline state, code being debugged, research corpora.
- **Safe to send after sanitization:** the specific draft/rubric for the escalated step, compressed summaries, the user's own goal text.
- **Dry-run preview + inspect-before-send:** yes to both — before any external call the user sees the *exact* payload and its token/cost estimate and must approve. This is the single most important control.
- **Secret detection before every cloud call:** run a scanner (e.g., **gitleaks** or Yelp **detect-secrets**) over the outbound payload; block on any hit. Both are standard, free, and support pre-commit/CI integration. This maps to OWASP Top 10 for LLM Applications (2025): LLM01 Prompt Injection (the #1 risk for the second consecutive edition), LLM02 Sensitive Information Disclosure, and LLM06 Excessive Agency.
- **Prompt-injection posture:** treat any retrieved/file content as untrusted. Adopt the **dual-LLM / quarantine pattern** (Simon Willison, 2023) — a privileged LLM holds tools/plans but never reads untrusted content, while a quarantined LLM reads untrusted content but has no tools and returns only structured/symbolic output. Google DeepMind's CaMeL extends this: per Debenedetti et al., "Defeating Prompt Injections by Design" (arXiv:2503.18813), CaMeL solved "77% of tasks with provable security (compared to 84% with an undefended system) in AgentDojo." Apply the pattern so a privileged cloud call never sees raw untrusted tokens directly.
- **API-key storage:** local `.env` only (already git-ignored), loaded via `python-dotenv`; never logged, never committed; redact in all logs.
- **Provider retention:** prefer providers with strong defaults. Anthropic's Claude API does not use API data for model training and, per multiple 2026 sources, reduced standard API log retention from 30 to **7 days** (effective September 14, 2025), with Zero Data Retention available for qualifying accounts (Messages and Token-Counting APIs are ZDR-eligible per Anthropic docs). OpenAI's API defaults to 30-day retention with no training by default; DeepSeek offers no ZDR and should carry a warning.
- **Audit trail:** every cloud request logged with redacted payload hash, provider, model, tokens, cost, and approval event; stored in SQLite for later review in Streamlit.

## 10. Cost controls

- **Pre-call estimate:** count tokens with the provider's own counter (Anthropic `count_tokens` endpoint; `tiktoken` for OpenAI-family) — character/4 heuristics are unreliable for code and undercount tool/schema overhead, and tiktoken "typically undercounts other model families, especially on code or non-English text." Sonnet 5's tokenizer shift (1.0–1.35×) makes provider-native counting mandatory for accuracy.
- **Budgets:** per-run max, daily, and monthly caps in config. **Block the call if the estimate exceeds the cap** (fail closed), showing the user the number and letting them raise the cap explicitly.
- **Local compression before cloud:** summarize/trim state locally to cut input tokens before any external call; "cloud only for final synthesis" and "cloud only after local failure" are the two cheapest patterns.
- **Post-call:** save actual input/output tokens and computed cost per provider into SQLite; show a running total and per-run cost in Streamlit; keep a cost history table.
- **Quality-vs-cost setting:** yes — expose a slider mapping to (a) local-only, (b) cloud-Judge-only, (c) cloud-Synthesizer-only, (d) cloud-on-hard-steps, (e) frontier-max. This mirrors Anthropic's own `effort` control and Gemini's Model Optimizer cost/quality/balance modes.

## 11. Implementation plan for the current repo

Design goal: **add fallback without rewriting the project.** Reuse the existing adapter layer, config loader, logger, and SQLite.

**`config/models.yaml`** — add a `cloud` block (disabled by default):
```yaml
cloud:
  enabled: false
  default_provider: anthropic
  providers:
    anthropic: { model: claude-sonnet-5, api_key_env: ANTHROPIC_API_KEY }
    google:    { model: gemini-3.1-pro,  api_key_env: GEMINI_API_KEY }
    deepseek:  { model: deepseek-v3.2,   api_key_env: DEEPSEEK_API_KEY, sensitive_warn: true }
  roles_allowed: [judge, synthesizer]     # conservative default
  budget: { per_run_usd: 0.25, daily_usd: 2.00, monthly_usd: 20.00, block_over_budget: true }
  privacy: { require_preview: true, scan_secrets: true, redact_logs: true }
  triggers: { low_judge_score: 55, tests_fail_repeats: 2, latency_budget_s: 300, user_frontier: true }
```
**`orchestrator/adapters.py`** — flesh out the (currently placeholder) provider stubs behind a common `BaseAdapter.generate(prompt, **opts)` interface: `OllamaAdapter` (existing HTTP call to `localhost:11434`), plus real `AnthropicAdapter`, `OpenAIAdapter`, `GoogleAdapter`, `DeepSeekAdapter`, each reading its key from env and returning `(text, usage_tokens)`.
**`orchestrator/router.py`** (new) — given `(role, mode, local_result, triggers, budget)`, decide local vs. cloud and which payload tier; returns a routing decision object, no LLM calls itself.
**`orchestrator/cloud_policy.py`** (new) — evaluates the policy matrix; enforces `roles_allowed`, approval requirement, and mode.
**`orchestrator/cost_tracker.py`** (new) — pre-call estimate, budget check (fail-closed), post-call actuals, SQLite writes.
**`orchestrator/privacy_guard.py`** (new) — secret scan (gitleaks/detect-secrets), PII regex, payload sanitizer/compressor, dry-run preview builder.
**`run.py`** — wrap each `_log_agent_call` so that after the local call the router may escalate; add `--allow-cloud`, `--cloud-provider`, `--max-cost`, `--frontier` flags; extend `run_summary.json` with a `fallback_events[]` array.
**`app/streamlit_app.py`** — add a Cloud panel: enable toggle, provider/model pick, budget inputs, live cost meter, per-call preview/approve dialog, and a fallback-events view.
**SQLite schema** — add `cloud_calls(run_id, role, provider, model, tokens_in, tokens_out, est_cost, actual_cost, reason, approved, ts)` and a `cost_daily` rollup; extend the runs table with `cloud_cost_total`.
**Logging** — add `fallback_trigger`, `cloud_request`, `cloud_response`, `budget_block` events.

## 12. Testing and evaluation plan for fallback

- **Unit:** router decisions per trigger; cost estimate vs. known token counts; budget fail-closed; policy matrix role gating.
- **Mock-provider tests:** a `FakeCloudAdapter` returning fixed text+usage so integration tests run offline and free.
- **Privacy-guard tests:** planted fake secrets (`AKIA…EXAMPLE`, dummy keys) must be blocked; PII regex fixtures; sanitizer removes `.env`-style content.
- **Secret-redaction tests:** logs never contain raw keys.
- **Fallback-trigger tests:** low-score, repeated-test-failure, timeout, context-overflow each fire exactly once and log correctly.
- **Regression suite (local-only vs. fallback):** same goal set run both ways; assert fallback improves the target metric enough to justify the cost.
- **Benchmark suite metrics:** quality delta (Judge + human), constraint-compliance rate, runtime, USD cost, #cloud calls, tokens sent to cloud, privacy-risk level (secrets blocked/leaked), user-approval events, failure-recovery rate. A fallback is "worth it" only if quality delta clears a preset threshold per dollar.

## 13. Defining Sonnet 5-level workflow quality

Anthropic positions Sonnet 5 as its most agentic Sonnet, matching Opus 4.8 on some agentic tasks at higher effort, with lower hallucination/sycophancy than 4.6 and self-checking of outputs. Per TechCrunch (June 30, 2026), "Sonnet 5 scores a 63.2% on agentic coding, compared to Opus 4.8's 69.2% and Sonnet 4.6's 58.1%" (SWE-bench Pro). Because full third-party evals for Sonnet 5 are still thin, define the target across measurable axes and use fair proxies:

| Axis | Sonnet 5 target (proxy) | Fairest proxy source |
|---|---|---|
| General reasoning | High | Sonnet 5 / Sonnet 4.6 published composites |
| Coding (single/multi-file) | ~63% SWE-bench-Pro-class | Anthropic Sonnet 5 figures |
| Long-horizon agentic completion | "Finishes tasks that stall" | Anthropic partner statements (Zapier, Lovable) |
| Strict constraint following | Very high | Deterministic check on our side |
| Citation reliability | High | Our citation verifier |
| Long context | 1M native | Anthropic docs |
| Speed/latency | Fast for tier | Anthropic |
| Cost | $2/$10 intro → $3/$15 | Anthropic pricing |
| Privacy | Cloud (7-day retention, ZDR option) | Anthropic data docs |

Crucially distinguish: **model quality** (raw Sonnet 5), **workflow quality** (multi-pass loop output), **agent-system quality** (routing+tools+memory+validators), and **product quality** (UX, history, reproducibility, cost transparency). Local Orchestrator competes on the last three, not the first.

## 14. Can Local AI Orchestrator reach that level?

**Yes for narrow, verifiable task classes; no for open-ended single-shot reasoning.** The research base is strong:
- **Reflexion** (Shinn et al., arXiv:2303.11366): "Reflexion achieves a 91% pass@1 accuracy on the HumanEval coding benchmark, surpassing the previous state-of-the-art GPT-4 that achieves 80%."
- **Self-Refine** (Madaan et al., arXiv:2303.17651): "GPT-4's performance increases by 8.7 units for code optimization when augmented using Self-Refine" (and +13.9 units on code readability).
- **Verifier-guided refinement** ("Self-Trained Verification…", arXiv:2605.30290): an STV-guided Qwen3-8B generator beat the 4× larger Qwen3-32B generator on hard reasoning splits, evidence that "a good verifier provides gains beyond what a much stronger generator can achieve."
- **Execution/test feedback** (CRITIC, Self-Debugging) reliably beats single-shot on code.

The orchestrator already has the two hardest pieces — a deterministic code verifier and a scored improvement loop — so on constraint-checked writing, test-passing single-file code, and citation-verified research it can reach practical parity with a Sonnet 5 single shot. It will *not* match Sonnet 5 on cross-repo refactors, novel long-horizon planning, or open-ended reasoning where local 14B models plateau; those are exactly where cloud fallback earns its cost.

## 15. Architecture path to approach Sonnet 5-level output

- **Local (default):** Supervisor, Planner, Critic, Builder/Fixer for routine work, first-pass Judge, Synthesizer.
- **Deterministic code (never a model):** code execution, pytest, word-count/format validators, citation-URL verification, secret/PII scanning, cost estimation, budget enforcement, routing decisions.
- **Retrieval (local):** RAG over prior runs and local docs (already on the roadmap) to feed context instead of enlarging prompts.
- **Memory (local):** persist Reflexion-style critiques in SQLite and replay them into later loops.
- **Cloud-assisted (opt-in, gated):** cross-family **Judge** (bias reduction/calibration), final **Synthesizer** polish, and **Builder/Fixer** only on repeatedly failing hard code; **long-context** steps routed to Gemini 3.1 Pro.
- **Human-approved:** every external call (preview + budget).
- **Continuously measured:** the benchmark suite in §17 runs on each release.

Answering the required questions directly: **(3) local** = all seven roles by default + retrieval + memory; **cloud-assisted** = Judge, Synthesizer, hard Builder/Fixer, long-context; **deterministic code** = verifier, validators, citation checks, secret scan, cost/budget/routing. **(4)** measure closeness via the eval suite (constraint compliance, test pass@1, citation validity, human preference win-rate vs. a Sonnet 5 single shot, cost, latency). **(5)** first, deterministic validators + cross-family cloud Judge (biggest quality/$); second, cloud Synthesizer + cost/privacy guards; third, retrieval/memory + cloud Builder/Fixer for hard code.

## 16. Task-by-task comparison matrix

Legend: **B**=clearly below Sonnet single-shot · **≈**=close · **=**=equal in practical output · **A**=above Sonnet single-shot · **C**=only realistic with cloud fallback.

| Task type | v1.0.0 local | v1.1 (validators/routing) | v1.2 (retrieval/memory) | v1.3 (deep research) | v2.0 (coding/tools) | v2.x (local+fallback) | Sonnet 5 single-shot | Sonnet 5 agent workflow |
|---|---|---|---|---|---|---|---|---|
| Short writing | ≈ | = | = | = | = | = | ref | A |
| Strict word-count writing | B | **A** | A | A | A | A | ref | A |
| Resume/portfolio | B | ≈ | = | = | = | = | ref | A |
| Coding w/ tests (single-file) | ≈ | = | = | = | **A** | A | ref | A |
| Debugging | B | ≈ | ≈ | ≈ | = | =/C | ref | A |
| Multi-file coding | B | B | B | B | ≈ | **C** | ref | A |
| Research reports | B | ≈ | ≈ | = | = | = | ref | A |
| Citation-heavy research | B | ≈ | ≈ | **=** (verifier) | = | = | ref | A |
| Planning | B | ≈ | ≈ | ≈ | ≈ | =/C | ref | A |
| Study explanations | ≈ | = | = | = | = | = | ref | A |
| Long-context project | B | B | ≈ (retrieval) | ≈ | ≈ | **C** | ref | A |
| Agentic repo work | B | B | B | B | ≈ | **C** | ref | A |
| UI/product ideation | ≈ | = | = | = | = | = | ref | A |
| Security-sensitive local | **A** (privacy) | A | A | A | A | A (local-only) | B (must upload) | B |

Reasoning: deterministic validators flip strict-format tasks *above* a Sonnet single-shot (the model may miss a hard constraint the validator enforces). Verifier + test loops equalize single-file coding and citation tasks. Multi-file/agentic/long-context remain cloud-only. Security-sensitive local tasks are the one column where the local system *beats* Sonnet 5, because using Sonnet 5 requires sending data off-device.

## 17. Benchmark/eval suite

| # | Task name | Type | Ground truth / scoring | Deterministic checks | LLM-judge | Human | Runtime target | Cost target | Pass threshold |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 120-word explainer | strict writing | exact word count | word-count validator | quality rubric | spot | <3 min local | $0 | count exact + rubric ≥80 |
| 2 | `fibonacci(n)` + pytest | coding | tests pass | pytest_runner | — | — | <4 min | $0 | 100% tests |
| 3 | Multi-file refactor | multi-file coding | test suite green | pytest across files | — | review | <8 min | ≤$0.10 (fallback) | tests pass |
| 4 | Cited 300-word brief | citation research | every URL resolves + supports claim | URL fetch + match | claim-support judge | spot | <6 min | ≤$0.05 | 100% citations valid |
| 5 | Retrieval over run history | RAG | correct prior-run facts | exact-match on stored fields | — | — | <2 min | $0 | ≥90% recall |
| 6 | Long-context summary | long context | key-point coverage | keyword coverage | coverage judge | — | <5 min | ≤$0.10 (Gemini) | ≥85% coverage |
| 7 | Cost-vs-quality A/B | tradeoff | quality delta / $ | cost_tracker | cross-family judge | — | n/a | budget-bound | delta/$ ≥ threshold |
| 8 | Privacy red-team | security | planted secrets blocked | gitleaks/detect-secrets | — | — | n/a | $0 | 0 leaks |
| 9 | Fallback-trigger test | routing | correct trigger fires | assertion on log | — | — | n/a | mocked | exact trigger |
| 10 | Constraint stress | strict format | format spec met | format validator | — | — | <4 min | $0 | 100% format |

## 18. Recommended roadmap

**Phase 1 (implement first — biggest quality/$, lowest risk):** deterministic validators (word-count, format, citation-URL) wired into the loop; cost/privacy scaffolding (`privacy_guard.py`, `cost_tracker.py`); **cross-family cloud Judge** behind `cloud.enabled` + preview + budget. This directly fixes the 120-word-constraint failure and improves the score signal that drives everything.
**Phase 2:** **cloud Synthesizer** final-polish option; full policy matrix + `router.py`/`cloud_policy.py`; Streamlit cost meter, preview/approve dialog, fallback-events view; SQLite `cloud_calls` table.
**Phase 3:** retrieval/memory (RAG over runs + reflection replay); **cloud Builder/Fixer** for repeatedly failing hard code; long-context routing to Gemini 3.1 Pro; the full benchmark suite in CI.
**Benchmarks that change the plan:** if the local cross-family Judge reaches ≥0.8 agreement with human ratings, deprioritize cloud Judge; if fallback quality-delta/$ falls below threshold on the A/B eval, keep those steps local; if local coding pass@1 on single-file tasks exceeds ~90%, don't spend cloud budget there.

## 19. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Secret/PII leak to cloud | Medium | High | Off-by-default, secret scan + PII regex before every call, preview/approve, redacted logs |
| Prompt injection via retrieved/file content | Medium | High | Dual-LLM/quarantine pattern; treat all external content as untrusted; deterministic output contracts |
| Runaway cost | Medium | Medium | Fail-closed budgets (per-run/daily/monthly), provider-native token counting, cost meter |
| Over-claiming "beats Sonnet 5" | Medium | High (credibility) | Honest positioning (§20); matrix shows only narrow parity |
| Local Judge miscalibration | High | Medium | Cross-family cloud Judge; human agreement checks |
| Provider outage/rate limits | Medium | Low | Multi-provider config; local-first fallback *back* to local |
| Stub adapters mistaken for working | High | Medium | Treat README "stubs exist" as scaffolding; implement real adapters in Phase 1 |
| Sonnet 5 tokenizer under-estimate | Medium | Low | Use Anthropic `count_tokens`; add 1.35× safety margin |
| Latency (12m49s) undermines UX | High | Medium | Latency-budget trigger; faster local default; cloud escalation only when needed |

## 20. Final recommendation

Ship **local-first with cloud disabled by default**, then add fallback as a gated, per-role escalation whose default beneficiaries are the **Judge** (cross-family, bias-reducing) and **Synthesizer** (final polish), using **Claude Sonnet 5** as the default provider, with **deterministic validators doing the constraint work that a bigger model would otherwise be needed for**. Do not buy hardware — the bottlenecks are architectural. Do not go cloud-only — it defeats the project's privacy premise and the evidence shows local-first is sufficient for the verifiable task classes. Implement validators + cross-family cloud Judge first, cloud Synthesizer + cost/privacy guards second, retrieval/memory + cloud Builder/Fixer third. Position the project honestly as a **privacy-first, verifier-guided, local-first agent workflow with optional frontier fallback** — impressive precisely because it is true.

**Portfolio positioning assets:**
- *One-line:* "A privacy-first, local-first multi-agent AI quality pipeline with deterministic verification and optional frontier-model fallback."
- *GitHub About:* "Local-first multi-agent AI orchestrator on Ollama — critique/revise/judge loop with deterministic code + citation verification, run history, and opt-in cloud fallback."
- *Portfolio summary:* "Built a local-first agent workflow that improves LLM output through scored critique loops and deterministic validators, reaching practical parity with frontier single-shot output on constraint-checked and test-verified tasks, with an opt-in, cost- and privacy-governed cloud fallback."
- *Resume bullet:* "Designed and built a local-first multi-agent AI pipeline (Python, Ollama, SQLite, Streamlit) with deterministic code/pytest verification, LLM-as-judge scoring loops, and an opt-in cloud-fallback layer with secret-scanning, token-based budgets, and audit logging."
- *Case-study title:* "Workflow Quality Over Model Quality: Reaching Frontier-Grade Output on a 24 GB MacBook."
- *Honest limitations:* not a Claude Code clone; no true 1M-token local context; local models don't match Sonnet 5 on multi-file/agentic/long-context tasks; cloud fallback trades some privacy for quality and is off by default.

---

### Key assumptions stated
1. **Sonnet 5 is real and current** (Anthropic, June 30, 2026; `claude-sonnet-5`; 1M context; $2/$10 intro → $3/$15). Where direct public benchmarks are thin, fair proxies (Sonnet 4.6, published Sonnet 5 SWE-bench-Pro figures, partner statements, and deterministic checks on our own side) are used and labeled.
2. **"Reach Sonnet 5-level quality" means workflow/agent-system/product parity on verifiable task classes**, not turning a local model into Sonnet 5.
3. **"Claude Code-inspired" = public/legal patterns only** (dual-LLM quarantine, effort/cost controls, verifier loops) — no proprietary internals copied.
4. **Repo internals not directly readable** (`adapters.py`, `models.yaml`, `database.py`) are treated as unverified and flagged; all pipeline/config/logging/SQLite claims that *are* asserted were verified by reading `run.py` and `README.md` directly.