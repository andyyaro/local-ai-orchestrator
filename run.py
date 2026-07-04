"""
run.py

Main entry point for the Local AI Orchestrator terminal pipeline.
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from agents.supervisor import SupervisorAgent
from agents.planner import PlannerAgent
from agents.builder import BuilderAgent
from agents.critic import CriticAgent
from agents.fixer import FixerAgent
from agents.judge import JudgeAgent
from agents.synthesizer import SynthesizerAgent
from orchestrator.cloud_policy import should_attempt_cloud, request_human_approval
from orchestrator.config_loader import get_active_profile, get_cloud_config, get_model_for_role, get_num_ctx_for_profile
from orchestrator.cost_tracker import check_budget, estimate_cost, record_call
from orchestrator.database import save_run, init_db
from orchestrator.code_runner import verify_draft_code, verification_failed
from orchestrator.logger import get_logger
from orchestrator.metrics import RunMetrics
from orchestrator.privacy_guard import PrivacyGuardError, build_minimal_payload, guard_payload
from orchestrator.resilience import FatalModelError
from orchestrator.router import classify_path, get_path_config
from orchestrator.validators import (
    run_validators,
    apply_validator_results_to_verdict,
    should_break_on_hard_fail,
)


DEFAULT_MAX_LOOPS = 3
DEFAULT_THRESHOLD = 70
DEFAULT_MIN_IMPROVEMENT = 5
RUNS_DIR = Path("runs")


def make_run_dir() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RUNS_DIR / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def save(run_dir: Path, filename: str, content: str):
    path = run_dir / filename
    path.write_text(content, encoding="utf-8")
    print(f"    → saved: {path.name}")


def header(step: str, label: str):
    print()
    print("╔" + "═" * 58 + "╗")
    print(f"║  {step:<8} {label:<46}  ║")
    print("╚" + "═" * 58 + "╝")


def score_bar(score: int, width: int = 40) -> str:
    filled = int(score / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {score}/100"


def _role_model(role: str, mode: str, model_main: str | None,
                model_fast: str | None) -> str:
    """Return model for role, honoring CLI overrides when supplied."""
    if model_fast and role in {"supervisor", "planner", "critic"}:
        return model_fast
    if model_main and role in {"builder", "fixer", "judge", "synthesizer"}:
        return model_main
    return get_model_for_role(role, mode)


def _collect_iterations(run_dir: Path, scores: list[int]) -> list[dict]:
    """Load saved loop artifacts so they can be stored in SQLite."""
    iterations_data = []
    for i, score in enumerate(scores, start=1):
        critique_path = run_dir / f"loop{i:02d}_critic.txt"
        fixer_path = run_dir / f"loop{i:02d}_fixer.txt"
        judge_path = run_dir / f"loop{i:02d}_judge.json"
        iterations_data.append({
            "iteration": i,
            "critique": critique_path.read_text(encoding="utf-8")
                        if critique_path.exists() else "",
            "revised_draft": fixer_path.read_text(encoding="utf-8")
                             if fixer_path.exists() else "",
            "verdict": json.loads(judge_path.read_text(encoding="utf-8"))
                       if judge_path.exists() else {},
            "score": score,
        })
    return iterations_data


def _log_agent_call(log, metrics: RunMetrics, agent_name: str, model: str,
                    call_fn, iteration: int = 0, on_step=None):
    """
    Run one agent call with Section 19 structured start/end/error logging.

    `on_step`, if given, is called with a plain event dict
    ({"type": "step", "agent": ..., "status": "running"|"done", ...}) both
    before and after the call -- this is the Phase 8 hook that lets
    app/streamlit_app.py post progress to its UI without run_pipeline()
    needing to know anything about Streamlit or a queue. Terminal usage
    (main()) never passes this, so CLI behavior is unchanged.
    """
    if on_step:
        on_step({"type": "step", "agent": agent_name, "status": "running"})
    t0 = time.time()
    log.agent_start(agent_name, model, iteration=iteration)
    try:
        result = call_fn()
        elapsed_ms = int((time.time() - t0) * 1000)
        log.agent_end(agent_name, chars=len(str(result)), elapsed_ms=elapsed_ms)
        metrics.record_agent_call(agent_name, model, elapsed_ms)
        if on_step:
            on_step({"type": "step", "agent": agent_name, "status": "done", "output": str(result)})
        return result
    except Exception as exc:
        log.error(agent_name, str(exc))
        if on_step:
            on_step({"type": "error", "message": str(exc)})
        raise


def _apply_code_verification_to_verdict(verdict: dict, code_feedback: str,
                                        threshold: int) -> dict:
    """Force a hard fail when coding-mode verification finds broken code."""
    if not code_feedback or not verification_failed(code_feedback):
        return verdict

    hard_fails = verdict.get("hard_fails", [])
    if not isinstance(hard_fails, list):
        hard_fails = []
    if "broken_code" not in hard_fails:
        hard_fails.append("broken_code")

    verdict["hard_fails"] = hard_fails
    verdict["pass"] = False
    verdict["total_score"] = 0
    verdict["rationale"] = (
        str(verdict.get("rationale", ""))
        + "\n\nCode verification failed before Judge pass/fail was accepted. "
        + "Broken or blocked code cannot pass regardless of model score."
    ).strip()
    verdict["code_verification"] = code_feedback
    print("  [Code Verification] Hard fail: broken_code overrides Judge score")
    return verdict


def _run_critic_fixer_judge_iteration(
    *, log, metrics: RunMetrics, run_dir: Path, summary: dict,
    iteration: int, refined_goal: str, goal: str, draft: str, mode: str,
    critic: CriticAgent, critic_model: str,
    fixer: FixerAgent, fixer_model: str,
    judge: JudgeAgent, judge_model: str,
    effective_threshold: int,
    previous_code_feedback: str, previous_validator_feedback: str,
    on_step=None,
) -> tuple[str, dict, int, str, str]:
    """
    Run one Critic -> Fixer -> (code verification) -> validate -> Judge
    pass. Shared by the normal/deep Critic/Fixer loop and the fast path's
    repair fallback (see run_pipeline) so both apply identical constraint
    enforcement instead of maintaining two copies of this logic.

    Threads the previous iteration's code-verification feedback (coding
    mode) and deterministic validator feedback (any mode) into the
    critique before it reaches the Fixer, so a constraint violation isn't
    just re-flagged -- the Fixer gets concrete, actionable direction (e.g.
    the exact word count to hit) rather than having to re-discover it.

    Returns (revised_draft, verdict, score, code_feedback, validator_feedback)
    where validator_feedback is this iteration's failed-validator detail
    text, to be threaded into the NEXT iteration via the same parameter.
    """
    print(f"  [Critic] Reviewing draft (iteration {iteration})...")
    critique = _log_agent_call(
        log, metrics, "critic", critic_model,
        lambda: critic.run(goal=refined_goal, draft=draft),
        iteration=iteration, on_step=on_step,
    )
    if previous_code_feedback:
        critique += (
            "\n\nCODE VERIFICATION FEEDBACK FROM PREVIOUS REVISION:\n"
            f"{previous_code_feedback}\n"
            "The next revision must fix these execution issues."
        )
    if previous_validator_feedback:
        critique += (
            "\n\nDETERMINISTIC CONSTRAINT FEEDBACK FROM PREVIOUS REVISION:\n"
            f"{previous_validator_feedback}\n"
            "The next revision MUST satisfy this constraint exactly (for "
            "example, hitting a required word count), even if it means "
            "shortening or restructuring the draft."
        )
    save(run_dir, f"loop{iteration:02d}_critic.txt", critique)

    revised = _log_agent_call(
        log, metrics, "fixer", fixer_model,
        lambda: fixer.run(
            goal=refined_goal,
            draft=draft,
            critique=critique,
            iteration=iteration,
            mode=mode,
        ),
        iteration=iteration, on_step=on_step,
    )
    save(run_dir, f"loop{iteration:02d}_fixer.txt", revised)

    code_feedback = ""
    if mode == "coding":
        print("  [Code Verification] Running extracted Python code...")
        code_feedback = verify_draft_code(revised)
        code_failed = verification_failed(code_feedback)
        code_run_file = f"loop{iteration:02d}_code_run.txt"
        save(run_dir, code_run_file, code_feedback)
        summary["code_verification"].append({
            "iteration": iteration,
            "failed": code_failed,
            "feedback_file": code_run_file,
        })
        first_line = code_feedback.splitlines()[0] if code_feedback else "No feedback"
        log.code_verification(
            iteration=iteration,
            success=not code_failed,
            hard_fail=code_failed,
            summary=first_line,
        )
        print(f"  [Code Verification] {first_line}")

    validator_results = run_validators(refined_goal, revised, mode, original_goal=goal)
    save(
        run_dir,
        f"loop{iteration:02d}_validators.json",
        json.dumps([r.__dict__ for r in validator_results], indent=2),
    )

    verdict = _log_agent_call(
        log, metrics, "judge", judge_model,
        lambda: judge.run(
            goal=refined_goal,
            draft=revised,
            iteration=iteration,
            mode=mode,
        ),
        iteration=iteration, on_step=on_step,
    )
    if mode == "coding":
        verdict = _apply_code_verification_to_verdict(verdict, code_feedback, effective_threshold)
    verdict = apply_validator_results_to_verdict(verdict, validator_results)
    save(run_dir, f"loop{iteration:02d}_judge.json", json.dumps(verdict, indent=2))
    for result in validator_results:
        if not result.passed:
            metrics.record_validator_failure(result.rule)
    for reason in verdict.get("hard_fails", []):
        metrics.record_hard_fail(reason)

    score = int(verdict["total_score"])
    log.score(
        iteration=iteration,
        score=score,
        passed=bool(verdict["pass"]),
        category_scores=verdict.get("scores", {}),
        hard_fails=verdict.get("hard_fails", []),
    )
    print(f"    Score: {score_bar(score)}")

    failed_validators = [r for r in validator_results if not r.passed]
    validator_feedback = "; ".join(r.detail for r in failed_validators)

    return revised, verdict, score, code_feedback, validator_feedback


def _maybe_escalate_to_cloud(
    role: str, goal: str, draft: str, allow_cloud: bool,
    run_id: int | None = None, rubric: str = "",
) -> str | None:
    """
    Attempt an optional, human-gated Phase 7 cloud escalation for `role`'s
    step. Returns the cloud response text if a real call actually happened
    and succeeded, or None if escalation was skipped, declined, or
    unavailable for any reason -- callers must always be prepared to keep
    using the local result exactly as the pipeline does without this
    function existing at all.

    All five conditions from the Phase 7 guide must hold before anything
    beyond a print statement happens: --allow-cloud passed (`allow_cloud`),
    cloud.enabled true and provider not "ollama" plus the role allow-listed
    (should_attempt_cloud), the privacy guard passing, the budget check
    passing, and interactive human approval. Missing any one silently
    falls back to None. The real adapter (orchestrator.adapters.AnthropicAdapter)
    still raises NotImplementedError pending model/pricing verification
    (see that class's docstring), so this currently can never actually
    replace a local result -- it exists as tested, gated scaffolding.
    """
    if not allow_cloud or not should_attempt_cloud(role):
        return None

    try:
        payload = guard_payload(
            role, build_minimal_payload(role, goal, draft, extra={"rubric": rubric})
        )
    except PrivacyGuardError as exc:
        print(f"  [Cloud] Escalation for '{role}' blocked by privacy guard: {exc}")
        return None

    # Rough, conservative token estimate for a pre-call budget check --
    # real tokenization differs; see cost_tracker.estimate_cost docstring.
    input_tokens = max(1, len(payload) // 4)
    output_tokens = input_tokens
    estimated_cost = estimate_cost(input_tokens, output_tokens)

    if not check_budget(estimated_cost):
        print(f"  [Cloud] Escalation for '{role}' declined: estimated cost "
              f"${estimated_cost:.4f} would exceed the configured budget.")
        return None

    if not request_human_approval(role, payload, estimated_cost):
        print(f"  [Cloud] Escalation for '{role}' declined by user.")
        return None

    cloud_config = get_cloud_config()
    model = cloud_config.get("model", "")
    record_call(run_id, role, model, input_tokens, output_tokens, estimated_cost, approved=True)

    from orchestrator.adapters import get_cloud_adapter
    try:
        adapter = get_cloud_adapter()
        return adapter.call(model=model, prompt=payload)
    except NotImplementedError as exc:
        print(f"  [Cloud] Real cloud adapter is not yet implemented: {exc}")
        return None


def run_pipeline(
    goal: str,
    model_main: str | None,
    model_fast: str | None,
    max_loops: int | None,
    threshold: int | None,
    min_improvement: int,
    run_dir: Path,
    path_override: str | None = None,
    allow_cloud: bool = False,
    on_step=None,
) -> tuple[dict, str]:
    """
    Run the full pipeline and return (summary, final_output).

    `on_step`, if given, is called with a plain event dict for each agent
    call ({"type": "step", ...}), each loop boundary ({"type": "loop_start"
    / "loop_result", ...}), and any mid-run error ({"type": "error", ...}).
    This is the Phase 8 hook that lets app/streamlit_app.py drive its live
    progress UI by calling this same function from a background thread,
    instead of maintaining its own separate pipeline implementation. When
    `on_step` is None (the terminal `main()` path), this function's
    behavior is identical to before Phase 8 -- only `print()`/log output.
    """
    log = get_logger(run_dir.name)
    metrics = RunMetrics(run_dir.name)
    pipeline_start = time.time()
    run_num_ctx = get_num_ctx_for_profile()

    summary = {
        "goal": goal,
        "active_profile": get_active_profile(),
        "model_main_override": model_main,
        "model_fast_override": model_fast,
        "role_models": {},
        "iterations_run": 0,
        "scores": [],
        "code_verification": [],
        "stop_reason": "",
        "final_score": 0,
        "passed": False,
    }

    header("STEP 1", "SUPERVISOR — Refine goal & choose mode")
    supervisor_model = _role_model("supervisor", "general", model_main, model_fast)
    summary["role_models"]["supervisor"] = supervisor_model
    supervisor = SupervisorAgent(model=supervisor_model, metrics=metrics, num_ctx=run_num_ctx)
    sup_result = _log_agent_call(
        log,
        metrics,
        "supervisor",
        supervisor_model,
        lambda: supervisor.run(goal=goal),
        on_step=on_step,
    )
    refined_goal = sup_result["refined_goal"]
    mode = sup_result["mode"]
    summary["mode"] = mode
    save(run_dir, "00_supervisor.json", json.dumps(sup_result, indent=2))
    print(f"    Refined goal : {refined_goal}")
    print(f"    Mode         : {mode}")

    path = classify_path(refined_goal, mode, override=path_override)
    path_config = get_path_config(path)
    effective_max_loops = max_loops if max_loops is not None else path_config["max_loops"]
    effective_threshold = threshold if threshold is not None else path_config["threshold"]
    summary["path"] = path
    summary["max_loops"] = effective_max_loops
    summary["threshold"] = effective_threshold
    log.path_selected(path)
    metrics.record_path(path)
    print(f"    Path         : {path}")

    log.run_start(
        goal=goal,
        model_main=model_main or "config-driven",
        model_fast=model_fast or "config-driven",
        max_loops=effective_max_loops,
        threshold=effective_threshold,
    )

    if path_config["skip_planner"]:
        plan = refined_goal
        planner_model = _role_model("planner", mode, model_main, model_fast)
        summary["role_models"]["planner"] = planner_model
        print("    Planner skipped (fast path) — refined goal used directly as plan")
    else:
        header("STEP 2", "PLANNER — Create execution plan")
        planner_model = _role_model("planner", mode, model_main, model_fast)
        summary["role_models"]["planner"] = planner_model
        planner = PlannerAgent(model=planner_model, metrics=metrics, num_ctx=run_num_ctx)
        plan = _log_agent_call(
            log,
            metrics,
            "planner",
            planner_model,
            lambda: planner.run(goal=refined_goal, mode=mode),
            on_step=on_step,
        )
        save(run_dir, "01_planner_plan.txt", plan)
        print(f"    Plan length  : {len(plan)} chars")

    header("STEP 3", "BUILDER — Write first draft")
    builder_model = _role_model("builder", mode, model_main, model_fast)
    summary["role_models"]["builder"] = builder_model
    builder = BuilderAgent(model=builder_model, metrics=metrics, num_ctx=run_num_ctx)
    draft = _log_agent_call(
        log,
        metrics,
        "builder",
        builder_model,
        lambda: builder.run(goal=refined_goal, plan=plan, mode=mode),
        on_step=on_step,
    )
    save(run_dir, "02_builder_draft_v0.txt", draft)
    print(f"    Draft length : {len(draft)} chars")

    best_draft = draft
    best_score = 0
    previous_score = 0
    previous_code_feedback = ""
    previous_validator_feedback = ""
    stop_reason = "max_loops"

    judge_model = _role_model("judge", mode, model_main, model_fast)
    summary["role_models"]["judge"] = judge_model
    judge = JudgeAgent(model=judge_model, pass_threshold=effective_threshold, metrics=metrics, num_ctx=run_num_ctx)

    # Constructed unconditionally (cheap -- no model call happens until
    # .run() is invoked) so the fast path can fall back to a Critic/Fixer
    # repair attempt on a repairable validator failure without needing a
    # separate code path to build these agents.
    critic_model = _role_model("critic", mode, model_main, model_fast)
    fixer_model = _role_model("fixer", mode, model_main, model_fast)
    summary["role_models"].update({
        "critic": critic_model,
        "fixer": fixer_model,
    })
    critic = CriticAgent(model=critic_model, metrics=metrics, num_ctx=run_num_ctx)
    fixer = FixerAgent(model=fixer_model, metrics=metrics, num_ctx=run_num_ctx)

    if path_config["skip_critic_fixer_loop"]:
        iteration = 1
        summary["iterations_run"] = iteration
        header(f"LOOP {iteration}/1", "VERIFY → JUDGE (fast path, no critic/fixer)")
        if on_step:
            on_step({"type": "loop_start", "iteration": iteration, "max_loops": effective_max_loops})

        revised = draft
        code_feedback = ""
        if mode == "coding":
            print("  [Code Verification] Running extracted Python code...")
            code_feedback = verify_draft_code(revised)
            code_failed = verification_failed(code_feedback)
            code_run_file = f"loop{iteration:02d}_code_run.txt"
            save(run_dir, code_run_file, code_feedback)
            summary["code_verification"].append({
                "iteration": iteration,
                "failed": code_failed,
                "feedback_file": code_run_file,
            })
            first_line = code_feedback.splitlines()[0] if code_feedback else "No feedback"
            log.code_verification(
                iteration=iteration,
                success=not code_failed,
                hard_fail=code_failed,
                summary=first_line,
            )
            print(f"  [Code Verification] {first_line}")

        validator_results = run_validators(refined_goal, revised, mode, original_goal=goal)
        save(
            run_dir,
            f"loop{iteration:02d}_validators.json",
            json.dumps([r.__dict__ for r in validator_results], indent=2),
        )

        verdict = _log_agent_call(
            log,
            metrics,
            "judge",
            judge_model,
            lambda: judge.run(
                goal=refined_goal,
                draft=revised,
                iteration=iteration,
                mode=mode,
            ),
            iteration=iteration, on_step=on_step,
        )
        if mode == "coding":
            verdict = _apply_code_verification_to_verdict(verdict, code_feedback, effective_threshold)
        verdict = apply_validator_results_to_verdict(verdict, validator_results)
        save(run_dir, f"loop{iteration:02d}_judge.json", json.dumps(verdict, indent=2))
        for result in validator_results:
            if not result.passed:
                metrics.record_validator_failure(result.rule)
        for reason in verdict.get("hard_fails", []):
            metrics.record_hard_fail(reason)

        score = int(verdict["total_score"])
        summary["scores"].append(score)
        log.score(
            iteration=iteration,
            score=score,
            passed=bool(verdict["pass"]),
            category_scores=verdict.get("scores", {}),
            hard_fails=verdict.get("hard_fails", []),
        )
        print(f"    Score: {score_bar(score)}")
        if on_step:
            on_step({
                "type": "loop_result", "iteration": iteration, "score": score,
                "scores": summary["scores"].copy(), "passed": bool(verdict.get("pass")),
            })

        best_score = score
        best_draft = revised
        save(run_dir, "best_draft.txt", best_draft)
        draft = revised

        failed_validators = [r for r in validator_results if not r.passed]
        previous_code_feedback = code_feedback
        previous_validator_feedback = "; ".join(r.detail for r in failed_validators)

        if verdict["pass"]:
            stop_reason = f"passed (score {score} >= threshold {effective_threshold})"
        elif verdict.get("hard_fails") and not should_break_on_hard_fail(
            mode, verdict, iteration, effective_max_loops
        ):
            # The fast path normally skips Critic/Fixer entirely, but a
            # repairable constraint violation (e.g. a word-count miss)
            # deserves a real repair attempt rather than an immediate,
            # avoidable failure -- fall back to the same Critic/Fixer/Judge
            # loop the normal/deep paths use for the remaining iterations.
            print("  [Repair] Fast path validator failure is repairable -- "
                  "falling back to Critic/Fixer for remaining iterations.")
            stop_reason = f"max_loops ({effective_max_loops}) reached"
            for iteration in range(2, effective_max_loops + 1):
                summary["iterations_run"] = iteration
                header(f"LOOP {iteration}/{effective_max_loops}", "REPAIR: CRITIC → FIXER → VERIFY → JUDGE")
                if on_step:
                    on_step({"type": "loop_start", "iteration": iteration, "max_loops": effective_max_loops})

                revised, verdict, score, code_feedback, validator_feedback = _run_critic_fixer_judge_iteration(
                    log=log, metrics=metrics, run_dir=run_dir, summary=summary,
                    iteration=iteration, refined_goal=refined_goal, goal=goal,
                    draft=draft, mode=mode,
                    critic=critic, critic_model=critic_model,
                    fixer=fixer, fixer_model=fixer_model,
                    judge=judge, judge_model=judge_model,
                    effective_threshold=effective_threshold,
                    previous_code_feedback=previous_code_feedback,
                    previous_validator_feedback=previous_validator_feedback,
                    on_step=on_step,
                )
                summary["scores"].append(score)
                draft = revised

                if on_step:
                    on_step({
                        "type": "loop_result", "iteration": iteration, "score": score,
                        "scores": summary["scores"].copy(), "passed": bool(verdict.get("pass")),
                    })

                if score > best_score and not (mode == "coding" and verification_failed(code_feedback)):
                    best_score = score
                    best_draft = revised
                    save(run_dir, "best_draft.txt", best_draft)

                if verdict["pass"]:
                    stop_reason = f"passed (score {score} >= threshold {effective_threshold})"
                    break

                if should_break_on_hard_fail(mode, verdict, iteration, effective_max_loops):
                    stop_reason = f"hard_fail: {verdict['hard_fails']}"
                    break

                previous_code_feedback = code_feedback
                previous_validator_feedback = validator_feedback
        elif verdict.get("hard_fails"):
            stop_reason = f"hard_fail: {verdict['hard_fails']}"
        else:
            stop_reason = f"fast path single iteration complete (score {score})"
    else:
        for iteration in range(1, effective_max_loops + 1):
            summary["iterations_run"] = iteration
            header(f"LOOP {iteration}/{effective_max_loops}", "CRITIC → FIXER → VERIFY → JUDGE")
            if on_step:
                on_step({"type": "loop_start", "iteration": iteration, "max_loops": effective_max_loops})

            revised, verdict, score, code_feedback, validator_feedback = _run_critic_fixer_judge_iteration(
                log=log, metrics=metrics, run_dir=run_dir, summary=summary,
                iteration=iteration, refined_goal=refined_goal, goal=goal,
                draft=draft, mode=mode,
                critic=critic, critic_model=critic_model,
                fixer=fixer, fixer_model=fixer_model,
                judge=judge, judge_model=judge_model,
                effective_threshold=effective_threshold,
                previous_code_feedback=previous_code_feedback,
                previous_validator_feedback=previous_validator_feedback,
                on_step=on_step,
            )
            summary["scores"].append(score)

            if on_step:
                on_step({
                    "type": "loop_result", "iteration": iteration, "score": score,
                    "scores": summary["scores"].copy(), "passed": bool(verdict.get("pass")),
                })

            if score > best_score and not (mode == "coding" and verification_failed(code_feedback)):
                best_score = score
                best_draft = revised
                save(run_dir, "best_draft.txt", best_draft)

            if verdict["pass"]:
                stop_reason = f"passed (score {score} >= threshold {effective_threshold})"
                draft = revised
                break

            if iteration > 1:
                improvement = score - previous_score
                if improvement < min_improvement and not (mode == "coding" and verification_failed(code_feedback)):
                    stop_reason = (
                        f"stalled (improvement {improvement} < "
                        f"min_improvement {min_improvement})"
                    )
                    draft = revised
                    break

            if should_break_on_hard_fail(mode, verdict, iteration, effective_max_loops):
                stop_reason = f"hard_fail: {verdict['hard_fails']}"
                draft = revised
                break

            previous_score = score
            previous_code_feedback = code_feedback
            previous_validator_feedback = validator_feedback
            draft = revised
        else:
            stop_reason = f"max_loops ({effective_max_loops}) reached"

    header("FINAL", "SYNTHESIZER — Polish best draft")
    synthesizer_model = _role_model("synthesizer", mode, model_main, model_fast)
    summary["role_models"]["synthesizer"] = synthesizer_model
    synthesizer = SynthesizerAgent(model=synthesizer_model, metrics=metrics, num_ctx=run_num_ctx)
    final_output = _log_agent_call(
        log,
        metrics,
        "synthesizer",
        synthesizer_model,
        lambda: synthesizer.run(
            goal=goal,
            best_draft=best_draft,
            score=best_score,
            iterations=summary["iterations_run"],
        ),
        on_step=on_step,
    )

    # Phase 7: optional, human-gated cloud escalation for the synthesizer
    # step. Off by default -- see _maybe_escalate_to_cloud's docstring for
    # the five conditions that must all hold before anything beyond a
    # print statement happens. Whatever comes back (local or cloud) is
    # still subject to the same final-output constraint guard below, so a
    # cloud response can no more bypass validation than a local one can.
    cloud_output = _maybe_escalate_to_cloud(
        role="synthesizer", goal=goal, draft=best_draft, allow_cloud=allow_cloud,
    )
    if cloud_output:
        print("  [Cloud] Using cloud-escalated synthesizer output.")
        final_output = cloud_output

    final_validator_results = run_validators(goal, final_output, mode)
    save(
        run_dir,
        "final_validators.json",
        json.dumps([r.__dict__ for r in final_validator_results], indent=2),
    )
    final_failed = [r for r in final_validator_results if not r.passed]
    if final_failed:
        detail = "; ".join(r.detail for r in final_failed)
        print(f"  [Synthesizer] Final output violates constraint(s), reverting to "
              f"pre-synthesis best draft: {detail}")
        log.error("synthesizer", f"final output violated constraint(s), reverted "
                  f"to best_draft: {detail}")
        metrics.record_hard_fail("synthesizer_constraint_violation")
        final_output = best_draft

    save(run_dir, "final_output.txt", final_output)

    summary["stop_reason"] = stop_reason
    summary["final_score"] = best_score
    summary["passed"] = best_score >= effective_threshold
    total_elapsed_ms = int((time.time() - pipeline_start) * 1000)
    summary["metrics"] = metrics.finalize(total_elapsed_ms)
    save(run_dir, "run_summary.json", json.dumps(summary, indent=2))

    log.stop(
        reason=stop_reason,
        final_score=best_score,
        iterations=summary["iterations_run"],
    )

    iterations_data = _collect_iterations(run_dir, summary["scores"])
    db_run_id = save_run(
        goal=goal,
        refined_goal=refined_goal,
        mode=mode,
        model_main=model_main or builder_model,
        model_fast=model_fast or judge_model,
        final_score=best_score,
        passed=(best_score >= effective_threshold),
        stop_reason=stop_reason,
        scores=summary["scores"],
        run_dir=str(run_dir),
        final_output=final_output,
        iterations_data=iterations_data,
    )
    summary["db_run_id"] = db_run_id
    save(run_dir, "run_summary.json", json.dumps(summary, indent=2))
    print(f"    → saved to database (run ID: {db_run_id})")

    return summary, final_output


def main():
    parser = argparse.ArgumentParser(
        description="Local AI Orchestrator — full terminal pipeline"
    )
    parser.add_argument("--goal", required=True,
                        help="The goal or task for the pipeline.")
    parser.add_argument("--model-main", default=None,
                        help="Optional override for Builder/Fixer/Judge/Synthesizer.")
    parser.add_argument("--model-fast", default=None,
                        help="Optional override for Supervisor/Planner/Critic.")
    parser.add_argument("--max-loops", type=int, default=None,
                        help="Max improvement loops. Default: path-determined "
                             f"(falls back to {DEFAULT_MAX_LOOPS} for an unrecognized path).")
    parser.add_argument("--threshold", type=int, default=None,
                        help="Pass score (0-100). Default: path-determined "
                             f"(falls back to {DEFAULT_THRESHOLD} for an unrecognized path).")
    parser.add_argument("--min-improvement", type=int, default=DEFAULT_MIN_IMPROVEMENT,
                        help=f"Min score gain per loop before stopping. Default: {DEFAULT_MIN_IMPROVEMENT}")
    parser.add_argument("--path", choices=["auto", "fast", "normal", "deep"], default="auto",
                        help="Pipeline path. 'auto' classifies the goal automatically. Default: auto")
    parser.add_argument("--allow-cloud", action="store_true", default=False,
                        help="Allow an optional, human-approved cloud escalation for "
                             "judge/synthesizer steps. Off by default. Also requires "
                             "cloud.enabled: true in config/models.yaml -- missing "
                             "either one falls back to the local model result.")
    args = parser.parse_args()

    init_db()
    run_dir = make_run_dir()
    active_profile = get_active_profile()

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║         LOCAL AI ORCHESTRATOR — TERMINAL MVP            ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  Goal        : {args.goal[:70]}")
    print(f"  Profile     : {active_profile}")
    print(f"  Main model  : {args.model_main or 'config-driven'}")
    print(f"  Fast model  : {args.model_fast or 'config-driven'}")
    print(f"  Max loops   : {args.max_loops if args.max_loops is not None else 'auto (path-determined)'}")
    print(f"  Threshold   : {(str(args.threshold) + '/100') if args.threshold is not None else 'auto (path-determined)'}")
    print(f"  Path        : {args.path}")
    print(f"  Run dir     : {run_dir}")

    start = datetime.now()

    try:
        summary, final_output = run_pipeline(
            goal=args.goal,
            model_main=args.model_main,
            model_fast=args.model_fast,
            max_loops=args.max_loops,
            threshold=args.threshold,
            min_improvement=args.min_improvement,
            run_dir=run_dir,
            path_override=None if args.path == "auto" else args.path,
            allow_cloud=args.allow_cloud,
        )
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Run stopped by user.")
        print(f"Partial output saved to: {run_dir}/")
        sys.exit(0)
    except FatalModelError as e:
        print(f"\n\n[MODEL FAILURE] {e}")
        print(f"Partial output saved to: {run_dir}/")
        sys.exit(1)

    elapsed = (datetime.now() - start).seconds

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                    FINAL OUTPUT                         ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    print(final_output)

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                    RUN SUMMARY                          ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  Stop reason   : {summary['stop_reason']}")
    print(f"  Final score   : {score_bar(summary['final_score'])}")
    print(f"  Passed        : {'YES ✓' if summary['passed'] else 'NO ✗'}")
    print(f"  Path selected : {summary.get('path', 'n/a')}")
    print(f"  Loops run     : {summary['iterations_run']} / {summary['max_loops']}")
    if summary["scores"]:
        score_history = " → ".join(str(s) for s in summary["scores"])
        print(f"  Score history : {score_history}")
    if summary.get("code_verification"):
        failures = sum(1 for item in summary["code_verification"] if item["failed"])
        print(f"  Code checks   : {len(summary['code_verification'])} run, {failures} failed")
    if summary.get("db_run_id"):
        print(f"  Database ID   : {summary['db_run_id']}")
    print(f"  Time elapsed  : {elapsed}s")
    print(f"  Run saved to  : {run_dir}/")
    print()


if __name__ == "__main__":
    main()
