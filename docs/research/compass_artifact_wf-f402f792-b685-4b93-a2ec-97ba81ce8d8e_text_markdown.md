# Local AI Orchestrator: Deep Research & Architecture Strategy Report (v1.0.0 → v2.0)

## TL;DR

- **Your MacBook Pro (M3, 24 GB) is enough to build an excellent, portfolio-grade local-first agent quality pipeline — but not enough for a true 1M-token context window or frontier ("Fable 5") quality without optional cloud fallback.** The 12m49s runtime and the ignored 120-word limit are *architecture* problems, not hardware problems, and both are fixable in v1.1 with no new hardware.
- **The two highest-leverage fixes are (1) deterministic constraint validators in Python code** (word count/format belong in code, never in an LLM judge) **and (2) eliminating model-swapping plus adding fast/normal/deep tiered routing** (the swap between three different ~9 GB 14B models on a 24 GB machine is the dominant cause of the slow run).
- **Ambitious features are realistic if scoped correctly:** long-context-*equivalent* memory via local embeddings + sqlite-vec retrieval; a safe local coding-agent loop built on your existing pytest verifier; and internet-connected deep research with deterministic citation verification. True 1M-token attention, self-training of large models, and single-model frontier quality are the things to *not* attempt locally.

---

## Section A — Executive Summary

The single most important finding: your current MacBook Pro (M3, 24 GB) is enough to build an excellent, portfolio-grade *local-first agent quality pipeline*, but it is **not** enough for true 1M-token context or frontier ("Fable 5") quality without optional cloud fallback — and your 12m49s runtime and 120-word failure are architecture problems, not hardware problems, that you can fix in v1.1 without new hardware.

**What is realistic on the current Mac:** a fast/normal/deep tiered pipeline that finishes simple tasks in well under a minute; deterministic constraint enforcement (word counts, format) in code; retrieval-augmented "long-context-equivalent" memory via local embeddings + sqlite-vec; a safe local coding-agent subsystem; LoRA fine-tuning of ≤8–9B models; and a local deep-research subsystem with citation verification.

**What is NOT realistic locally:** a genuine 1,000,000-token attention context (KV cache alone would need ~64 GB even for a 7B model — KVQuant, Hooper et al., NeurIPS 2024, showed 1M-token LLaMA-7B inference requires "64GB for the KV cache" on an A100 *even at 2-bit KV quantization*); frontier-model reasoning quality from a single local model; and self-training/RLHF of large models.

**Top 5 improvements to prioritize:**
1. **Deterministic constraint validators in code** (word count, format, required sections, JSON schema) that gate the Judge — fixes the 120-word failure permanently.
2. **Tiered routing (fast/normal/deep)** + collapsing the 7-agent pipeline for simple tasks — the biggest runtime win.
3. **Model-swap elimination**: keep one model family resident; stop alternating three different 14B models per run.
4. **Timeout/resilience redesign** using per-model timeout budgets + bounded retries + fallback-to-smaller-model — NOT blind exponential backoff.
5. **Metrics/profiling** (per-agent latency, tokens, model-load events) so every later change is measured.

---

## Section B — Current Project Diagnosis

The repo (inspected directly: `run.py`, `README.md`, architecture diagram) is a serial 7-stage pipeline: Supervisor → Planner → Builder → [Critic → Fixer → (Verify) → Judge] loop → Synthesizer. `run.py`'s `_role_model()` routes "fast" roles (supervisor/planner/critic) to `--model-fast` and "main" roles (builder/fixer/judge/synthesizer) to `--model-main`, else falls back to `config/models.yaml`. Code verification correctly hard-fails broken code (`_apply_code_verification_to_verdict` forces `pass=False`, `total_score=0`, `broken_code`) so the Judge cannot override it — a genuinely good, defensible design. The loop already has three stop conditions: pass threshold, min-improvement stall detection, and hard-fail breaks (`_should_break_on_hard_fail`). Structured logging records `agent_start`/`agent_end` with `elapsed_ms`, and KeyboardInterrupt already saves partial output. This is a solid v1.0 foundation worth evolving, not replacing.

**Bottleneck 1 — model calls per run.** A single run with `max_loops=N` makes 3 + 4N sequential model calls (Supervisor, Planner, Builder, then Critic+Fixer+Judge per loop, plus Synthesizer; Verify is non-LLM). At N=4 that is 19 blocking, sequential model calls.

**Bottleneck 2 — model swapping (the dominant cause of 12m49s).** The pipeline alternates between "main" (14B, ~9 GB at Q4_K_M) and "fast" models, and across profiles references three different 14B models (qwen2.5:14b, qwen2.5-coder:14b, phi4:14b — all 9.0 GB at Q4_K_M). Two 14B models cannot be co-resident on 24 GB: macOS caps GPU-usable unified memory at ~66% (≈16 GB on 24 GB per InsiderLLM), and 2 × 9 GB = 18 GB of weights alone exceeds that before KV cache and the 3–4 GB macOS idle footprint. Ollama's FAQ confirms the swap behavior: "If there is insufficient available memory to load a new model request while one or more models are already loaded, all new requests will be queued until the new model can be loaded. As prior models become idle, one or more will be unloaded to make room for the new model." Each 14B cold-load from the internal SSD costs several seconds to ~30 s (a measured qwen2.5-coder:14b load was 29 s). Combined with a *realistic* 14B Q4_K_M decode rate of only ~8–15 tok/s on a base-M3-class chip (bandwidth-bound: tok/s ≈ memory-bandwidth ÷ model-GB × 0.6–0.8; base M3 ≈ 100 GB/s), a multi-agent run that generates several thousand output tokens plus repeated swaps easily reaches ~13 minutes. A 14B + a 3B (~2 GB) *can* co-reside; two 14Bs never can.

**Bottleneck 3 — no output-length or constraint control.** There is no deterministic validator; the Judge (an LLM) is trusted to notice a 120-word limit, and LLM judges are documented to be weak at exactly this kind of check.

**Bottleneck 4 — no metrics surfaced for optimization.** The logger records per-agent `elapsed_ms`, but nothing aggregates it to reveal *where* the 12m49s actually went (decode vs. load vs. prefill).

---

## Section C — Research Findings by Topic

### 12.1 One-million-token context locally
**What research says.** The KV cache scales as `2 × n_layers × n_kv_heads × head_dim × seq_len × bytes_per_element`. For a 7B-class model the KV cache at 128K tokens is already ~16 GB; at 1M tokens it is ~64–128 GB depending on precision — larger than the weights. Attention is quadratic in sequence length: RetrievalAttention (arXiv:2409.10516) reports that a 1M-token prompt for Llama-3-8B needs ~1,765 s per token without a cache and ~125 GB of KV cache with one. KVQuant (Hooper et al., NeurIPS 2024, arXiv:2401.18079) states its "nuq2 method enables serving the LLaMA-7B model with a context length of 1M tokens on a single A100 GPU (requiring 64GB for the KV cache)" — i.e., even aggressive 2-bit KV quantization needs 64 GB.
**What it means / feasibility on your Mac: impossible.** Ollama's usable GPU budget is ~16 GB on 24 GB; a 1M-token KV cache cannot fit by any configuration.
**Recommended approach — the best "1M-equivalent":** retrieval + hierarchical summarization + a local vector store. Keep run history/artifacts in SQLite (as today); index project files and prior runs with a local embedding model (nomic-embed-text via Ollama, 768-dim) into **sqlite-vec** (single-file, aligns with your SQLite-first design; brute-force search is fast for thousands–hundreds-of-thousands of vectors per its author Alex Garcia). Use hybrid search (SQLite FTS5 BM25 + vector), which research cited in the Hermes-agent knowledgebase issue shows "improves recall 15-30% over either method alone." Inject only top-k (5–10) chunks; keep chunks ≤512 tokens ("Quality drops sharply above ~2500 tokens per chunk"). Set a realistic working context (8K–32K `num_ctx`) explicitly.
**Risks/tradeoffs:** retrieval can miss context; mitigate with hybrid search and summaries. **Citations:** arXiv:2401.18079, arXiv:2409.10516, sqlite-vec (alexgarcia.xyz), Ollama FAQ.

### 12.2 Speed / runtime reduction
**What research says + means.** Two levers dominate: fewer/cheaper model calls, and no model swapping. Realistic 14B Q4_K_M decode on a base M3 is ~8–15 tok/s (bandwidth-bound); an 8B is ~24–28 tok/s on M4-class hardware (Pickuma). Ollama's default `keep_alive` is "5 minutes before being unloaded" (Ollama FAQ) but models unload earlier under memory pressure. A 9 GB model cold-loads in ~5–30 s from the internal SSD. Prefill/TTFT rises linearly with prompt length and can dominate on long agent prompts (Starmorph: at 8.5K context, "94% of time was spent prefilling").
**Design:** a **fast path** (single strong model, no loop) for simple tasks; a **normal path** (Builder + one Critic/Fixer/Judge loop); a **deep path** (full pipeline + retrieval). A cheap classifier (3B model or heuristics) picks the path. Stabilize/cache system prompts. Keep one model family resident; escalate to a second model only when necessary. **Reproducible measurement:** log per-agent latency, tokens in/out, model-load events, and path taken to `run_summary.json`. **Citations:** Ollama FAQ, Starmorph, Pickuma, Ante Kapetanovic benchmark.

### 12.3 Big-O / complexity
Current wall-clock ≈ `Σ_calls (load_cost + prefill(prompt_len) + decode(output_len))` over 3+4N calls. Prefill is O(prompt²) in attention but ~O(prompt·d) with cache; decode is O(output·context). Model swaps add a step-function `load_cost`. Retrieval changes prompt_len from O(history) to O(k) (constant) — the single biggest complexity improvement. Redesign: bounded-k retrieval, path selection to cut N, resident model to zero-out `load_cost`. **Measurement plan:** use the new metrics layer to attribute wall-clock to load vs. prefill vs. decode per agent.

### 12.4 Timeout & resilience — **do NOT use blind exponential backoff**
**What research says.** Exponential backoff + jitter is designed for *transient, network/rate-limit* failures (429/503) and multi-client contention ("thundering herd"); AWS's Builder Library notes that when "failures are caused by overload or contention, backing off often doesn't help as much as it seems," and best practice is to never retry non-retryable (4xx) errors, cap retries at 3–5, cap delay at 30–60 s, and always add jitter *if* retrying. Local Ollama timeouts are the opposite case: a single client, slow generation / resource contention / a model still loading. Retrying the identical call just wastes minutes and may re-trigger the same load.
**Recommended for this project:** per-model timeout *budgets* (a 14B gets a longer budget than a 3B); **failure classification** (model-not-loaded → wait/preload; OOM → fall back to a smaller model; genuine crash → fail fast). At most one retry for a true transient; otherwise **fall back to a smaller/faster model** rather than backing off. **Resume-from-artifact:** the pipeline already writes per-step artifacts to `runs/<ts>/`, so a `--resume` flag can reload the last good draft. Cooperative cancellation already exists via KeyboardInterrupt; add progress reporting. **Citation:** AWS Builder Library, knowledgelib.io, ByteByteGo.

### 12.5 Memory optimization
macOS idle takes 3–4 GB; Ollama's GPU budget is ~66% of 24 GB ≈ 16 GB; a 14B Q4_K_M is 9 GB + 1–4 GB KV cache. Therefore one 14B + one 3B (2 GB) can co-reside (~11–14 GB) but never two 14Bs (18 GB of weights > 16 GB budget). Set `num_ctx` explicitly (the default silently truncates and auto-sizes to VRAM, which caused your kind of instruction-loss bug). Enable Flash Attention (`OLLAMA_FLASH_ATTENTION=1`) and Q8 KV cache to cut KV memory ~30–50%. Streamlit overhead is minor (~0.3–1 GB). Avoid disk swap, which drops generation ~10–20x. **Citations:** Ollama FAQ, InsiderLLM, Easton Blog, Starmorph.

### 12.6 Self-improving workflow
**What research says.** LoRA/QLoRA on Apple Silicon via mlx-lm is feasible for small models: a Qwen 9B LoRA runs in ~2 hr for 600 iterations; a Mistral-7B QLoRA peaks ~7 GB (BuildMVPFast, willitrunai). Full fine-tuning is not feasible on 24 GB. But for a quality pipeline, **prompt optimization + evals + memory is more realistic and higher-ROI than training.** DSPy's MIPROv2 (Bayesian search over instructions + few-shot demos, no weight updates) delivers substantial structured-task gains: DeepEval/DSPy benchmarks lifted qwen2.5:0.5b math accuracy from 33.3% zero-shot to 55.6% (+22 points), and a 2025 study (arXiv:2511.11898) reports a median relative improvement of ~95% across model-task combinations, though a real-world agent case (arXiv:2507.03620) saw a more modest 87.5%→90% lift — so expect variance, and validate on your own eval set. Reflexion (Shinn et al., 2023, arXiv:2303.11366 — verbal self-reflection stored in memory, Ω=1–3 reflections) and Self-Refine (Madaan et al., 2023) give real gains but depend on a reliable evaluator. **LLM-as-judge is unreliable for hard constraints:** Zheng et al. (2023) documented position, verbosity, and self-preference/self-enhancement biases, and a 2026 review notes frontier judges "exceeded 50% error rates on challenging bias benchmarks."
**Safeguards:** deterministic validators for anything checkable; judge from a *different* model family than the generator; randomize option order; store successful runs as retrievable few-shot examples; require user approval before pulling any new model. **Citations:** arXiv:2303.11366, arXiv:2410.21819, arXiv:2511.11898, DeepEval docs, willitrunai MLX guide.

### 12.7 "true loop engineering"
**Not a recognized research term** — it is your own phrasing. Map it to established work: plan→act→observe→reflect (ReAct, Yao et al., arXiv:2210.03629), Reflexion (verbal RL with episodic + long-term memory), Self-Refine, Tree/Graph of Thoughts, evaluator-optimizer loops, and test-time compute / repeated sampling. For this project, "loop engineering" should mean: a **bounded, instrumented improvement loop** with (a) a deterministic gate *before* the LLM judge, (b) explicit stop conditions (already present), (c) anti-stall detection (already present via `min_improvement`), (d) reflections stored to memory and retrieved on the next run, and (e) a hard iteration cap to prevent infinite loops and "hallucinated progress" (a documented long-horizon failure mode). **Citation:** arXiv:2210.03629, arXiv:2303.11366.

### 12.8 Claude Code-style coding agent (public/legal patterns only)
**What research says.** SWE-agent (Yang, Jimenez, Wettig et al., NeurIPS 2024, arXiv:2405.15793) introduced the **Agent-Computer Interface (ACI)** — custom, structured file/edit/run commands beat naive tool access, achieving "a pass@1 rate of 12.5% [SWE-bench] and 87.7% [HumanEvalFix]… far exceeding the previous state-of-the-art achieved with non-interactive LMs." OpenHands uses event-driven, containerized, multi-agent delegation. Aider uses a repo map (AST + PageRank) plus model-specific edit formats and a two-list message state. The source-code taxonomy paper (arXiv:2604.03515) concludes "tool reliability matters more than model capability." Claude Code deliberately favors agentic exploration over RAG.
**Legal, original architecture:** a plan→read→edit→test→reflect loop with (1) an AST/ripgrep repo map, (2) a constrained patch/edit tool (diff application), (3) your existing sandboxed pytest verifier as the ground-truth signal, (4) a todo list in state, (5) a "minimal unnecessary changes" instruction, and (6) stop-when-tests-pass. This builds directly on your `code_runner.py` + `pytest_runner.py`. **Citations:** arXiv:2405.15793, arXiv:2604.03515, LangChain Open SWE blog.

### 12.9 Deep research capability
**What research says.** A University of Pennsylvania study ("Detecting and Correcting Reference Hallucinations…", arXiv:2604.03173) found "3–13% of citation URLs are hallucinated… while 5–18% are non-resolving overall. Deep research agents generate substantially more citations per query than search-augmented LLMs but hallucinate URLs at higher rates" (peaking at 13.3% in deep-research mode) — so *more* citations ≠ fewer errors. The fix that works: a **deterministic post-processing citation-verification pipeline** — record every URL actually retrieved (a SourceRegistry, per NVIDIA's AI-Q blueprint) and validate every citation in the report against it, dropping unverifiable ones. The same UPenn study shows a `urlhealth`-style verification tool cut non-resolving URLs with p<10⁻³⁵ and post-mitigation rates below 1%. **Workflow:** clarify → subquestions → search plan → search → open sources → extract evidence → score sources → claim map → contradictions/gaps → follow-up → draft → **verify every citation against retrieved sources** → final answer with uncertainty. **Citations:** arXiv:2604.03173, arXiv:2601.22984 (PING taxonomy of DRA hallucinations), NVIDIA AI-Q docs.

### 12.10 Internet / tool use safely
Prompt injection from web pages is the top risk. The best-practice defense is the **dual-LLM / quarantine pattern** (Simon Willison, 2023; operationalized by DeepMind's **CaMeL**, Debenedetti et al., arXiv:2503.18813, 2025): a Privileged LLM never sees untrusted web tokens; a Quarantined LLM (no tools) processes untrusted content and returns structured/labeled data via typed references. CaMeL "solv[es] 77% of tasks with provable security (compared to 84% with an undefended system) in AgentDojo" (v2, June 2025; the earlier v1 abstract cited 67%). Also: spotlighting/datamarking untrusted content, least-privilege tools, robots.txt/ToS respect, a network-access toggle, user approval before risky/destructive actions, and — per the OWASP LLM Prompt Injection cheat sheet — treat all web content as *data, not instructions*. **Citations:** arXiv:2503.18813, simonwillison.net, OWASP cheat sheet.

### 12.11 Constraint obedience (the 120-word failure)
**Deterministic validators belong in code, not the LLM judge.** Word count, format, required sections, forbidden content, and JSON schema are all exactly checkable in Python. Add a validator layer that runs *before* the Judge: if word count is out of range, trigger a targeted repair loop (or adjust the instruction) rather than asking the model to "try to be concise." Keep the Judge verdict JSON-schema-validated (it is already JSON). The LLM judge should only score subjective quality; hard constraints are pass/fail in Python. This is consistent with the LLM-as-judge literature (§12.6) showing judges are unreliable on surface constraints. **Citation:** arXiv:2410.21819, W&B "Exploring LLM-as-a-Judge."

### 12.12 Model & runtime strategy
**Best local models on 24 GB (2026):** general/main — a Qwen3-class 8–9B (fits at Q8, fast; willitrunai rates Qwen 3.5 9B 94/100 at ~38 tok/s on M4 Pro 24 GB) or a 14B dense at Q4_K_M (tight, slower); coding — **Qwen3-Coder 30B-A3B MoE** (3B active, ~17 GB at Q4_K_M, ~30 tok/s, 70.6% SWE-bench per Medium/Evalogical) is the standout *if* it fits, else your existing qwen2.5-coder:14b; reasoning — a distilled reasoning 14B (e.g., DeepSeek-R1-Distill-14B); embeddings — nomic-embed-text. **MoE (A3B) models give ~14B-class quality at ~3B speed and are the key unlock at 24 GB.** **Runtime:** Ollama is the right default for ergonomics; MLX is faster for sub-14B generation on Apple Silicon — the vllm-mlx paper (arXiv:2601.19139) reports "21% to 87% higher throughput than llama.cpp across models ranging from Qwen3-0.6B to Nemotron-30B" on an M4 Max, with the gap closing to near-zero at 27B+ — and MLX also enables LoRA, so add it as an optional backend later. Note Ollama's own MLX backend (v0.19, March 30 2026) requires an M5-family chip with 32 GB+, so it will *not* activate on your M3. Quantization: Q4_K_M is the sweet spot (~3.3% quality loss, 75% size reduction per Starmorph). **Realistic quality ceiling: strong but below frontier; a hybrid (local-first + optional cloud for the hardest judge/synthesis calls) is the only realistic path to frontier-level quality.** The OpenAI/Anthropic provider stubs already in your adapter layer make hybrid a config change, not a rewrite. **Decision matrix:** local-only (max privacy, capped quality) → local-first + optional cloud fallback (recommended: privacy by default, frontier quality on demand, pay-per-use) → external workstation (only if you want local 30B dense + long context routinely).

### 12.13 Hardware
The current Mac **handles:** 8–14B models, the tiered pipeline, retrieval, LoRA of small models, and deep research. It is **slow for:** 14B decode, multi-14B pipelines, and long context. **What helps most, ranked by cost-effectiveness:** (1) **free** — the architecture fixes (routing, no swapping, deterministic constraints); (2) **low/pay-per-use** — optional cloud API fallback for only the hardest calls (frontier quality without buying hardware; privacy tradeoff); (3) **$ recurring** — a search API subscription for deep research; (4) **$$$** — a 64–128 GB Mac Studio / higher-memory Apple Silicon unlocks 30B dense + longer context + larger LoRA; (5) an NVIDIA RTX box (24–32 GB VRAM) gives ~2–3x faster token gen but less unified capacity. **Bottom line: do the free architecture work first; buy nothing until metrics prove you need it.**

---

## Section D — Proposed v1.1 Architecture (evolve, not rewrite)

1. **Constraint layer (`orchestrator/validators.py`)**: deterministic word-count/format/section/JSON-schema checks; run before the Judge; feed failures into the Fixer as structured feedback; add a bounded repair loop.
2. **Tiered routing (`orchestrator/router.py`)**: classify task difficulty (heuristic + optional 3B classifier) → fast/normal/deep path; collapse the pipeline for simple tasks.
3. **Timeout/resilience (`orchestrator/adapters.py`)**: per-model timeout budgets, failure classification, ≤1 transient retry with jitter, fallback-to-smaller-model, `--resume` from artifact.
4. **Memory discipline**: pin one model family per run; set explicit `num_ctx`; enable Flash Attention + Q8 KV cache; never load two 14Bs.
5. **Judge/Synthesizer**: judge from a *different* model family than the generator; randomize; JSON-schema verdict; remove deterministic constraints from judge scope.
6. **Metrics (`orchestrator/metrics.py`)**: aggregate per-agent latency, tokens, model-load events, and path taken; surface in Streamlit + `run_summary.json`.

---

## Section E — Proposed v2.0 Architecture

- **Long-context-equivalent memory**: nomic-embed-text + sqlite-vec + FTS5 hybrid retrieval over project files, artifacts, and run history; hierarchical summarization; episodic (per-run) + archival (long-term) memory; store Reflexion-style reflections for reuse.
- **Deep research subsystem**: subquestion planner → search → extract → SourceRegistry → deterministic citation verification → report with explicit uncertainty.
- **Internet/tool use**: dual-LLM quarantine pattern; network toggle; user approval before risky actions; robots.txt/ToS respect.
- **Source/citation DB**: extend SQLite with `sources`, `claims`, a `claim→source` map, and verification status.
- **Agent loop engineering**: bounded plan-act-observe-reflect with deterministic gates, memory, and hard caps.
- **Coding-agent subsystem**: repo map (AST/ripgrep) + constrained patch tool + sandboxed pytest loop + todo state, built on `code_runner.py`/`pytest_runner.py`.
- **Self-improvement/evals**: DSPy/MIPROv2 prompt optimization offline; an eval suite of benchmark tasks; optional MLX LoRA for a small specialized model; a model registry with user-approved pulls.
- **Optional hybrid routing**: cloud API for only the hardest judge/synthesis calls via the existing adapter stubs.

---

## Section F — Model & Runtime Strategy

**Recommended routing table (role → model → quant → context → approx memory):**
- Supervisor / Planner / Classifier → llama3.2:3b → Q4_K_M → 8K → ~2 GB
- Builder / Fixer (general) → Qwen3-class 8–9B → Q4_K_M/Q8 → 8–16K → ~5–10 GB
- Builder / Fixer (coding) → qwen2.5-coder:14b, or Qwen3-Coder 30B-A3B (MoE) if it fits → Q4_K_M → 16–32K → ~9–17 GB
- Judge → different-family 8–14B → Q4_K_M → 8K → ~5–9 GB
- Synthesizer → same as Builder → Q4_K_M → 8K → ~5–9 GB
- Embeddings → nomic-embed-text → — → — → ~0.5 GB

**Keep:** Ollama, SQLite, config-driven routing, the code-verification hard-fail. **Replace:** multi-14B alternation → a single resident family + MoE for coding. **Add:** MLX as an optional backend for sub-14B speed and LoRA, sqlite-vec, deterministic validators, and the metrics layer. **Quantization strategy:** Q4_K_M as default; Q8 for a small model you can afford to keep resident; Q8 KV cache for long context.

---

## Section G — Hardware Strategy

The current Mac is sufficient for all of v1.1 and most of v2.0. Biggest improvement per dollar is **software architecture (free)**, then **optional cloud fallback** for the hardest calls (frontier quality without buying hardware), then a **64–128 GB Mac Studio / higher-memory Apple Silicon** if you want local 30B dense + long context + bigger LoRA routinely. An NVIDIA RTX box gives raw token-generation speed but less unified capacity (it cannot hold the large MoE/long-context configs a big-memory Mac can). A search API subscription is the main recurring cost for the deep-research subsystem. **Do not buy hardware until the metrics layer proves a specific bottleneck the architecture cannot solve.**

---

## Section H — Implementation Roadmap

1. **v1.1 constraint enforcement** — *goal:* obey word/format constraints (fixes the 120-word bug); *why:* correctness is the headline defect; *files:* new `orchestrator/validators.py`, `agents/judge.py`, `run.py`, `prompts/judge.txt`, `prompts/synthesizer.txt`; *difficulty:* low; *risk:* low; *tests:* word-count validator, schema validator, repair-loop; *verify:* a 120-word task passes; *don't touch:* the code-verifier hard-fail logic.
2. **v1.1 speed + timeout** — *goal:* cut runtime and harden failures; *files:* `orchestrator/router.py`, `orchestrator/adapters.py`, `run.py`, `config/models.yaml`; *difficulty:* medium; *risk:* medium; *tests:* path selection, model fallback, resume-from-artifact; *verify:* a simple task finishes <60 s and never loads two 14Bs; *don't touch:* the artifact schema.
3. **v1.1 metrics** — *goal:* measurement before further optimization; *files:* `orchestrator/metrics.py`, `orchestrator/logger.py`, `app/streamlit_app.py`; *difficulty:* low; *tests:* aggregation correctness; *verify:* per-agent load/prefill/decode breakdown visible.
4. **v1.2 memory + retrieval** — *goal:* long-context-equivalent memory; *files:* new `memory/`, `orchestrator/database.py`, embeddings via Ollama; *difficulty:* medium; *tests:* retrieval recall, top-k injection cap; *verify:* RAG over prior runs and project files works.
5. **v1.3 deep research prototype** — *goal:* cited research output; *files:* new `research/`, SourceRegistry, citation verifier; *difficulty:* high; *tests:* citation-verification drops unverifiable URLs; *verify:* zero unverifiable citations in output.
6. **v1.4 model routing + registry** — *goal:* best model per role + safe pulls; *files:* `config/models.yaml`, registry module; *difficulty:* medium; *tests:* routing, approval gate; *verify:* no model is pulled without user approval.
7. **v2.0 coding-agent / tool-use** — *goal:* repo-level coding assistance; *files:* new `coding_agent/`; *difficulty:* high; *tests:* patch/test loop, sandbox safety; *verify:* a multi-file task ends with passing tests.
8. **v2.0 self-improvement / evals** — *goal:* measured, safe improvement; *files:* new `evals/`, DSPy integration, optional MLX LoRA; *difficulty:* high; *tests:* eval regression suite; *verify:* MIPROv2 shows a lift on your held-out eval set.

---

## Section I — Complexity & Performance Plan

**Current model:** 3+4N sequential calls; prompt_len grows with history; model swaps add step-function load costs. **Proposed model:** bounded-k retrieval (constant prompt), path selection (cut N to 0–1 for simple tasks), a resident model (zero load cost). **Metrics to collect:** per-agent latency, tokens in/out, model-load count, path taken, total wall-clock, and the load/prefill/decode split. **Benchmark tasks:** a fixed suite (short writing with a word limit, coding with tests, planning, study/explanation). **Target runtimes** (simple-to-moderate tasks): fast path <30 s, normal <2 min, deep <5 min. **Regression tests:** assert both runtime *and* constraint-obedience thresholds so a future change that reintroduces the 120-word bug or the 13-minute run fails CI.

---

## Section J — Risk Register

- **Prompt injection from web** → dual-LLM quarantine pattern; treat web content as data; user approval; network toggle.
- **Hallucinated citations** → deterministic SourceRegistry verification; drop unverifiable URLs.
- **Bad LLM judges** → deterministic gates; cross-family judge; option randomization; never let the LLM judge hard constraints.
- **Infinite loops** → hard iteration cap (present) + stall detection (present).
- **Too many model calls** → tiered routing and early exit.
- **Memory overload** → single resident family; explicit `num_ctx`; no double-14B; avoid disk swap.
- **Overengineering** → stage gates; keep local-first simplicity; don't add heavy frameworks prematurely.
- **UX too complex** → keep Streamlit minimal with progressive disclosure.
- **Local-only quality ceiling** → optional cloud fallback for the hardest calls only.
- **Auto-downloading unsuitable models** → registry with mandatory user approval.
- **Training instability / impracticality** → prefer prompt optimization + evals; use LoRA only for small models with a held-out eval and user opt-in.

---

## Section K — Final Recommendation

**Do first:** v1.1 constraint enforcement (fixes the 120-word bug), then the speed/timeout redesign (fixes the 12m49s run), then the metrics layer. These three require no new hardware and address every current defect.

**Do NOT do yet:** fine-tuning / auto-training of large models, true 1M-token context, the full coding-agent, or any multi-framework rewrite.

**Answers to your 20 questions, directly:**
1–2. **True 1M-token context locally? No** — the KV cache alone (~64+ GB even for a 7B model) cannot fit in 24 GB. Use retrieval + hierarchical summarization + sqlite-vec as the "1M-equivalent." 3. **Why so slow?** Model swapping between three ~9 GB 14B models that can't co-reside on 24 GB, plus slow 14B decode (~8–15 tok/s) and repeated cold-loads. 4. **Fastest safe runtime cut:** tiered routing + one resident model family, keeping quality by escalating only when needed. 5. **Exponential backoff for local timeouts? No** — it's for transient/network failures; use per-model timeout budgets + failure classification + fallback-to-smaller-model. 6. **Fallback models:** on OOM/timeout, drop to a smaller model rather than retrying the same call. 7. **Auto-train locally? Not for large models;** LoRA of ≤8–9B is feasible via MLX but is not the right first move. 8. **Self-improvement basis:** prompt optimization (DSPy/MIPROv2) + evals + memory first; training last. 9. **Research says:** self-refinement/Reflexion/ReAct work but depend on a *reliable* evaluator, and LLM judges are biased — hence deterministic gates. 10. **Stronger coding agent without copying proprietary internals:** an ACI-style plan→read→edit→test→reflect loop on your existing sandboxed pytest verifier. 11. **Deep research:** subquestion planning + search + a SourceRegistry + deterministic citation verification. 12. **Prevent hallucinated citations:** verify every citation against actually-retrieved sources and drop the rest. 13. **Prompt-injection defense:** dual-LLM quarantine (Willison/CaMeL); treat web as data. 14. **Models per role:** see the Section F table (3B for light roles, 8–9B/MoE for heavy, cross-family judge, nomic-embed-text). 15. **Ollama enough?** Yes as the default; add MLX later for sub-14B speed and LoRA. 16. **Mac enough?** Yes for a strong local-first pipeline; no for frontier quality or true 1M context. 17. **Biggest upgrade if needed:** optional cloud fallback for the hardest calls (best value), then a 64–128 GB Mac. 18. **v1.1** = constraints + speed/timeout + metrics; **v1.2** = memory/retrieval; **v1.3** = deep research; **v1.4** = routing/registry; **v2.0** = coding agent + self-improvement/evals. 19. **Tests to add:** deterministic validator tests, path-selection tests, fallback/resume tests, citation-verification tests, and runtime + constraint regression tests. 20. **Absolutely avoid:** blind exponential backoff, chasing true 1M context, auto-downloading models without approval, letting the LLM judge enforce hard constraints, and rewriting the working v1.0 core.

**Is the current Mac enough?** Yes for a portfolio-grade local-first system. **Is true 1M-token context realistic?** No locally. **Is deep research realistic?** Yes, with a search API and deterministic citation verification. **Does frontier quality require hybrid/cloud?** Yes — a local-first architecture with optional cloud fallback for only the hardest judge/synthesis calls is the only realistic path to frontier-level output; keep everything else local.

---

### Assumptions stated
- "Fable 5 level of quality" is treated purely as a *quality target* (frontier/next-gen), with no proprietary internals copied.
- "true loop engineering" is treated as your own phrase and mapped to established agent-loop research (ReAct, Reflexion, Self-Refine, evaluator-optimizer, test-time compute).
- "Copy Claude Code" is interpreted as researching public/legal patterns (SWE-agent ACI, OpenHands, Aider) and proposing an original, legal architecture.
- The 24 GB machine is assumed to be a base-M3-class chip (~100 GB/s bandwidth); an M3 Pro would be somewhat faster but the conclusions hold.
- Some 2026 model/benchmark figures (e.g., Qwen3.6, base-M3 14B tok/s) come from vendor blogs and community benchmarks without standardized methodology and are flagged as directional, not definitive.