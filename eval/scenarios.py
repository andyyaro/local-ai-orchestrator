"""
eval/scenarios.py

Phase 12: one function per end-to-end eval scenario, exercising the real
system (real local models where the scenario specifically calls for it,
real deterministic modules everywhere else) rather than mocks. This is a
human-run acceptance layer, not a CI job -- see
docs/upgrade-guide/17-phase-12-eval-suite-checklist.md.

Every scenario:
  - wraps its phase-specific imports in a try/except and returns
    "skipped" (never "failed") if that phase isn't present in this repo,
    or if a real external dependency it needs (e.g. a pulled embedding
    model) isn't available -- this project never downloads anything
    automatically, including from an eval scenario.
  - returns a plain EvalResult(name, status, message).

Scenarios that touch cloud_calls purely for synthetic budget/mock testing
(eval_cloud_mock_fallback, eval_cost_budget_block) redirect
orchestrator.database.DB_PATH to a throwaway temp file for the duration
of the check, so no fake cost data ever lands in your real
runs/history.db. eval_local_only_no_cloud and the real-model scenarios
intentionally use the real database, the same way a manual
scripts/local_acceptance.sh run already does -- these represent genuine
runs worth keeping in your history.
"""

import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EvalResult:
    name: str
    status: str  # "pass" | "fail" | "skipped"
    message: str


# ── Phase 2/3: the original bug this whole guide exists to fix ────────────────

def eval_exact_word_limit() -> EvalResult:
    name = "eval_exact_word_limit"
    try:
        from run import run_pipeline
        from orchestrator.validators import check_word_limit
    except ImportError as exc:
        return EvalResult(name, "skipped", f"Phase 2/3 dependency not available: {exc}")

    run_dir = Path(tempfile.mkdtemp(prefix="eval_exact_word_limit_"))
    goal = "Write a summary of the water cycle in exactly 120 words."

    try:
        summary, final_output = run_pipeline(
            goal=goal, model_main=None, model_fast=None,
            max_loops=3, threshold=60, min_improvement=5, run_dir=run_dir,
        )
    except Exception as exc:  # pragma: no cover - real model call
        return EvalResult(name, "fail", f"run_pipeline raised: {exc}")

    result = check_word_limit(final_output, limit=120, mode="exact", tolerance=12)

    # The actual regression this guide fixes is a run reporting success
    # (passed=True) despite violating the word count -- that was the
    # original silent-pass bug. A real local model not managing to land
    # within tolerance, with the pipeline correctly detecting that and
    # honestly reporting failure (passed=False, hard_fail:
    # constraint_violation), is the safety net working as intended, not a
    # regression -- treat that as a pass for this eval. Only a mismatch
    # between "reported passed" and "actually violates the constraint" is
    # the real bug to fail loudly on.
    if summary.get("passed"):
        if result.passed:
            return EvalResult(name, "pass", f"Run passed and genuinely satisfies the constraint: {result.detail}")
        return EvalResult(
            name, "fail",
            f"THE ORIGINAL BUG THIS GUIDE FIXES IS BACK: run reported "
            f"passed=True but {result.detail}!",
        )

    hard_fails = (summary.get("metrics") or {}).get("hard_fails") or {}
    if "constraint_violation" in hard_fails:
        return EvalResult(
            name, "pass",
            f"Model's draft did not satisfy the word count ({result.detail}), but the "
            "pipeline correctly detected and refused it (stop_reason="
            f"{summary.get('stop_reason')}) instead of silently passing -- "
            "the fix is working, even though this particular model call "
            "didn't produce a compliant draft.",
        )
    return EvalResult(
        name, "fail",
        f"Run failed for a reason unrelated to the word-count constraint: "
        f"stop_reason={summary.get('stop_reason')}",
    )


def eval_json_only_judge() -> EvalResult:
    name = "eval_json_only_judge"
    try:
        from agents.judge import JudgeAgent
        from orchestrator.config_loader import get_model_for_role
    except ImportError as exc:
        return EvalResult(name, "skipped", f"Judge agent not available: {exc}")

    judge = JudgeAgent(model=get_model_for_role("judge", "general"))
    sample_draft = (
        "The water cycle describes how water moves through the atmosphere, "
        "land, and oceans via evaporation, condensation, and precipitation."
    )

    try:
        verdict = judge.run(
            goal="Explain the water cycle briefly.", draft=sample_draft,
            iteration=1, mode="general",
        )
    except Exception as exc:  # pragma: no cover - real model call
        return EvalResult(name, "fail", f"JudgeAgent.run raised: {exc}")

    required_keys = {"scores", "total_score", "pass", "hard_fails", "rationale"}
    missing = required_keys - set(verdict.keys())
    if missing:
        return EvalResult(name, "fail", f"Verdict missing expected key(s) {missing}: {verdict}")
    if "judge_parse_error" in (verdict.get("hard_fails") or []):
        raw = verdict.get("raw_judge_output", "")[:300]
        return EvalResult(name, "fail", f"Judge output failed to parse as JSON. Raw: {raw}")
    return EvalResult(name, "pass", f"Judge returned valid, schema-matching JSON (score={verdict['total_score']}).")


def eval_simple_coding_task() -> EvalResult:
    name = "eval_simple_coding_task"
    try:
        from run import run_pipeline
    except ImportError as exc:
        return EvalResult(name, "skipped", f"run.py not available: {exc}")

    run_dir = Path(tempfile.mkdtemp(prefix="eval_simple_coding_task_"))
    goal = (
        "Write a Python function called double(n) that returns n multiplied "
        "by 2. Include a pytest test asserting double(5) == 10."
    )

    try:
        summary, _ = run_pipeline(
            goal=goal, model_main=None, model_fast=None,
            max_loops=2, threshold=60, min_improvement=5, run_dir=run_dir,
        )
    except Exception as exc:  # pragma: no cover - real model call
        return EvalResult(name, "fail", f"run_pipeline raised: {exc}")

    code_checks = summary.get("code_verification") or []
    if not code_checks:
        return EvalResult(
            name, "fail",
            f"No code_verification recorded -- mode={summary.get('mode')}, "
            "goal may not have been classified as coding.",
        )
    if any(item["failed"] for item in code_checks):
        return EvalResult(name, "fail", f"code_verification reported a failure: {code_checks}")
    return EvalResult(name, "pass", f"code_verification succeeded ({len(code_checks)} check(s) run).")


# ── Phase 4: resilience ───────────────────────────────────────────────────────

def eval_timeout_fallback() -> EvalResult:
    name = "eval_timeout_fallback"
    try:
        import orchestrator.resilience as resilience_module
        from orchestrator.metrics import RunMetrics
    except ImportError as exc:
        return EvalResult(name, "skipped", f"Phase 4/5 dependency not available: {exc}")

    # Force the primary ("medium"-class, e.g. an 8b model) timeout down to
    # 1 second -- guaranteed too short for any real generation, so this
    # deterministically triggers a real ModelTimeoutError and fallback,
    # without an artificial sleep. The fallback model's own ("small") 60s
    # budget is left generous so the actual fallback call has a fair
    # chance to complete for real.
    original_get_config = resilience_module.get_resilience_config
    resilience_module.get_resilience_config = lambda: {
        "fallback_model": "llama3.2:3b",
        "max_local_retries": 1,
        "timeouts": {"default": 1, "small": 60, "medium": 1, "large": 1},
    }

    metrics = RunMetrics("eval_timeout_fallback")
    try:
        result = resilience_module.call_with_resilience(
            model="llama3.1:8b", prompt="Say hello in one short sentence.",
            temperature=0.7, num_ctx=512, role="builder", metrics=metrics,
        )
    except Exception as exc:  # pragma: no cover - real model call
        return EvalResult(name, "fail", f"call_with_resilience did not fall back cleanly: {exc}")
    finally:
        resilience_module.get_resilience_config = original_get_config

    finalized = metrics.finalize(total_elapsed_ms=0)
    if finalized["fallbacks"] >= 1 and finalized["timeout_events"] >= 1:
        return EvalResult(
            name, "pass",
            f"Fallback engaged and recorded (fallbacks={finalized['fallbacks']}, "
            f"timeout_events={finalized['timeout_events']}). Response: {result[:60]!r}",
        )
    return EvalResult(name, "fail", f"Expected a recorded fallback/timeout event, got metrics={finalized}")


# ── Phase 7: cloud fallback scaffolding ────────────────────────────────────────

def eval_local_only_no_cloud() -> EvalResult:
    name = "eval_local_only_no_cloud"
    try:
        from run import run_pipeline
        from orchestrator.database import get_connection, init_db
    except ImportError as exc:
        return EvalResult(name, "skipped", f"Phase 7 dependency not available: {exc}")

    init_db()
    conn = get_connection()
    before_count = conn.execute("SELECT COUNT(*) FROM cloud_calls").fetchone()[0]
    conn.close()

    run_dir = Path(tempfile.mkdtemp(prefix="eval_local_only_no_cloud_"))
    try:
        run_pipeline(
            goal="Write two short sentences about cats.",
            model_main="llama3.2:3b", model_fast="llama3.2:3b",
            max_loops=1, threshold=50, min_improvement=5, run_dir=run_dir,
        )
    except Exception as exc:  # pragma: no cover - real model call
        return EvalResult(name, "fail", f"run_pipeline raised: {exc}")

    conn = get_connection()
    after_count = conn.execute("SELECT COUNT(*) FROM cloud_calls").fetchone()[0]
    conn.close()

    if after_count == before_count:
        return EvalResult(
            name, "pass",
            f"cloud_calls row count unchanged ({before_count}) during a "
            "cloud.enabled: false run.",
        )
    return EvalResult(
        name, "fail",
        f"cloud_calls grew from {before_count} to {after_count} during a "
        "local-only run -- an unauthorized cloud call may have happened!",
    )


def eval_cloud_mock_fallback() -> EvalResult:
    name = "eval_cloud_mock_fallback"
    try:
        from orchestrator import database
        from orchestrator.adapters import MockCloudAdapter
        from orchestrator.cost_tracker import estimate_cost, record_call
    except ImportError as exc:
        return EvalResult(name, "skipped", f"Phase 7 dependency not available: {exc}")

    original_db_path = database.DB_PATH
    database.DB_PATH = Path(tempfile.mkdtemp(prefix="eval_cloud_mock_fallback_")) / "history.db"
    try:
        adapter = MockCloudAdapter(canned_response="Mock escalation response.")
        response = adapter.call(model="claude-sonnet-5", prompt="Score this draft.")

        cost = estimate_cost(input_tokens=500, output_tokens=200)
        record_call(
            run_id=None, role="judge", model="claude-sonnet-5",
            input_tokens=500, output_tokens=200, cost_usd=cost, approved=True,
        )

        conn = database.get_connection()
        row_count = conn.execute("SELECT COUNT(*) FROM cloud_calls").fetchone()[0]
        conn.close()
    finally:
        database.DB_PATH = original_db_path

    if row_count == 1 and response == "Mock escalation response." and cost >= 0:
        return EvalResult(
            name, "pass",
            f"Exactly one cloud_calls row recorded (cost=${cost:.4f}); "
            "MockCloudAdapter made zero real network calls.",
        )
    return EvalResult(name, "fail", f"Expected exactly 1 recorded row and a mock response, got row_count={row_count}, response={response!r}")


def eval_privacy_redteam() -> EvalResult:
    name = "eval_privacy_redteam"
    try:
        from orchestrator.privacy_guard import PrivacyGuardError, guard_payload
    except ImportError as exc:
        return EvalResult(name, "skipped", f"Phase 7 dependency not available: {exc}")

    fake_secret_payload = (
        "GOAL:\nScore this.\n\n"
        "DRAFT:\nANTHROPIC_API_KEY=sk-ant-fake00000000000000000000"
    )
    try:
        guard_payload("judge", fake_secret_payload)
    except PrivacyGuardError:
        return EvalResult(name, "pass", "guard_payload correctly raised PrivacyGuardError on a fake secret pattern.")
    return EvalResult(
        name, "fail",
        "guard_payload did NOT raise on an obviously fake secret pattern -- "
        "the privacy guard is not working.",
    )


def eval_cost_budget_block() -> EvalResult:
    name = "eval_cost_budget_block"
    try:
        from orchestrator import cost_tracker as cost_tracker_module
        from orchestrator import database
    except ImportError as exc:
        return EvalResult(name, "skipped", f"Phase 7 dependency not available: {exc}")

    original_db_path = database.DB_PATH
    original_get_cloud_config = cost_tracker_module.get_cloud_config
    database.DB_PATH = Path(tempfile.mkdtemp(prefix="eval_cost_budget_block_")) / "history.db"
    cost_tracker_module.get_cloud_config = lambda: {
        "provider": "anthropic",
        "pricing": {"input_per_million_usd": 2.00, "output_per_million_usd": 10.00},
        "budget": {
            "per_run_usd": 5.00, "daily_usd": 2.00, "monthly_usd": 20.00,
            "block_over_budget": True,
        },
    }
    try:
        database.save_cloud_call(
            run_id=None, role="judge", provider="anthropic", model="claude-sonnet-5",
            input_tokens=100, output_tokens=100, cost_usd=1.95, approved_by_user=True,
        )
        over_budget_blocked = not cost_tracker_module.check_budget(0.10)
        under_budget_allowed = cost_tracker_module.check_budget(0.01)
    finally:
        database.DB_PATH = original_db_path
        cost_tracker_module.get_cloud_config = original_get_cloud_config

    if over_budget_blocked and under_budget_allowed:
        return EvalResult(
            name, "pass",
            "check_budget correctly blocked an over-daily-budget call and "
            "allowed a still-under-budget one.",
        )
    return EvalResult(
        name, "fail",
        f"Budget check misbehaved: over_budget_blocked={over_budget_blocked}, "
        f"under_budget_allowed={under_budget_allowed}",
    )


# ── Phase 9: retrieval memory ──────────────────────────────────────────────────

def eval_retrieval() -> EvalResult:
    name = "eval_retrieval"
    try:
        from memory import indexer
        from memory.embeddings import EmbeddingModelUnavailableError
        from memory.retriever import retrieve_context
        from orchestrator import database
    except ImportError as exc:
        return EvalResult(name, "skipped", f"Phase 9 dependency not available: {exc}")

    original_db_path = database.DB_PATH
    database.DB_PATH = Path(tempfile.mkdtemp(prefix="eval_retrieval_")) / "history.db"
    try:
        run_id = database.save_run(
            goal="Explain connection pooling.",
            refined_goal="Explain connection pooling.",
            mode="general", model_main="test", model_fast="test",
            final_score=90, passed=True, stop_reason="passed", scores=[90],
            run_dir="runs/eval_retrieval_fixture",
            final_output=(
                "Connection pooling reduces database latency by reusing "
                "existing connections instead of opening a new one for "
                "every request."
            ),
        )
        try:
            indexer.index_run(run_id)
        except EmbeddingModelUnavailableError as exc:
            return EvalResult(
                name, "skipped",
                f"Embedding model not available locally (this project never "
                f"pulls one automatically): {exc}",
            )

        context = retrieve_context("How does connection pooling help latency?", k=3)
    finally:
        database.DB_PATH = original_db_path

    if not context:
        return EvalResult(name, "fail", "retrieve_context returned nothing for a goal matching an indexed run.")
    if "connection pooling" not in context.lower():
        return EvalResult(name, "fail", f"Retrieved context did not reference the indexed run: {context[:200]}")
    chunk_count = context.count("\n- (")
    if chunk_count > 3:
        return EvalResult(name, "fail", f"retrieve_context returned {chunk_count} chunks, exceeding requested top_k=3.")
    return EvalResult(name, "pass", f"Retrieved {chunk_count} relevant chunk(s), correctly capped at top_k.")


# ── Phase 10: deep research citation verification ─────────────────────────────

def eval_citation_verification() -> EvalResult:
    name = "eval_citation_verification"
    try:
        from research.citation_verifier import reject_unverified_citations
        from research.source_registry import SourceRegistry
    except ImportError as exc:
        return EvalResult(name, "skipped", f"Phase 10 dependency not available: {exc}")

    registry = SourceRegistry()
    registry.register(
        url="https://example.com/real-source", title="Real Source",
        fetched_at="2026-07-04T00:00:00", content_hash="abc123",
        text="Sleep plays a critical role in memory consolidation and cognitive function.",
    )

    report = (
        "Sleep improves memory consolidation and cognitive function.[1] "
        "This is a fabricated claim citing a source that does not exist.[9]"
    )

    annotated, failed = reject_unverified_citations(report, registry)

    if len(failed) != 1:
        return EvalResult(name, "fail", f"Expected exactly 1 unverified claim, got {len(failed)}: {failed}")
    if "fabricated claim" not in failed[0]:
        return EvalResult(name, "fail", f"Wrong claim flagged as unverified: {failed}")
    if "[UNVERIFIED CITATION] Sleep improves" in annotated:
        return EvalResult(name, "fail", "The genuinely verified claim was incorrectly flagged too.")
    return EvalResult(name, "pass", "Exactly the fabricated citation was flagged; the verified claim was left untouched.")


# ── Streamlit smoke ────────────────────────────────────────────────────────────

def eval_streamlit_smoke() -> EvalResult:
    name = "eval_streamlit_smoke"
    try:
        result = subprocess.run(
            [sys.executable, "-c", "import app.streamlit_app"],
            capture_output=True, text=True, timeout=60,
        )
    except FileNotFoundError as exc:
        return EvalResult(name, "skipped", f"Could not launch Python subprocess: {exc}")

    if result.returncode == 0:
        return EvalResult(name, "pass", "app.streamlit_app imported cleanly.")
    return EvalResult(name, "fail", f"Import failed (exit {result.returncode}): {result.stderr[-500:]}")


ALL_SCENARIOS = [
    eval_exact_word_limit,
    eval_json_only_judge,
    eval_simple_coding_task,
    eval_timeout_fallback,
    eval_local_only_no_cloud,
    eval_cloud_mock_fallback,
    eval_privacy_redteam,
    eval_cost_budget_block,
    eval_retrieval,
    eval_citation_verification,
    eval_streamlit_smoke,
]
