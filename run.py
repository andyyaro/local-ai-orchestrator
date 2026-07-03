"""
run.py

Main entry point for the Local AI Orchestrator terminal pipeline.

Pipeline:
  Supervisor → Planner → Builder → [Critic → Fixer → Judge] × N → Synthesizer

The loop repeats until the Judge passes the output, max loops is reached,
or improvement stalls.

Usage:
    python run.py --goal "Your goal here"
    python run.py --goal "..." --max-loops 5 --threshold 75
    python run.py --goal "..." --model-main llama3.1:8b --model-fast llama3.2:3b
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from agents.supervisor import SupervisorAgent
from agents.planner import PlannerAgent
from agents.builder import BuilderAgent
from agents.critic import CriticAgent
from agents.fixer import FixerAgent
from agents.judge import JudgeAgent
from agents.synthesizer import SynthesizerAgent


# ── Defaults ──────────────────────────────────────────────────────────────────
# These are fallback constants only. The actual models come from config/models.yaml
# via get_model_for_role(). Switch active_profile there to change quality level.
DEFAULT_MODEL_MAIN = "llama3.2:3b"   # Bootstrap — override via --model-main
DEFAULT_MODEL_FAST = "llama3.2:3b"
DEFAULT_MAX_LOOPS = 3
DEFAULT_THRESHOLD = 70
DEFAULT_MIN_IMPROVEMENT = 5   # stop looping if score improves by less than this

RUNS_DIR = Path("runs")


# ── Helpers ───────────────────────────────────────────────────────────────────

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
    """Render a simple ASCII progress bar for the score."""
    filled = int(score / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {score}/100"


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(
    goal: str,
    model_main: str,
    model_fast: str,
    max_loops: int,
    threshold: int,
    min_improvement: int,
    run_dir: Path,
) -> dict:
    """
    Execute the full pipeline and return a summary dict.
    """

    summary = {
        "goal": goal,
        "model_main": model_main,
        "model_fast": model_fast,
        "threshold": threshold,
        "max_loops": max_loops,
        "iterations_run": 0,
        "scores": [],
        "stop_reason": "",
        "final_score": 0,
        "passed": False,
    }

    # ── SUPERVISOR ────────────────────────────────────────────────────────────
    header("STEP 1", "SUPERVISOR — Refine goal & choose mode")
    supervisor = SupervisorAgent(model=model_fast)
    sup_result = supervisor.run(goal=goal)
    refined_goal = sup_result["refined_goal"]
    mode = sup_result["mode"]
    save(run_dir, "00_supervisor.json", json.dumps(sup_result, indent=2))
    print(f"    Refined goal : {refined_goal}")
    print(f"    Mode         : {mode}")

    # ── PLANNER ───────────────────────────────────────────────────────────────
    header("STEP 2", "PLANNER — Create execution plan")
    planner = PlannerAgent(model=model_fast)
    plan = planner.run(goal=refined_goal, mode=mode)
    save(run_dir, "01_planner_plan.txt", plan)
    print(f"    Plan length  : {len(plan)} chars")

    # ── BUILDER (first draft) ─────────────────────────────────────────────────
    header("STEP 3", "BUILDER — Write first draft")
    builder = BuilderAgent(model=model_main)
    draft = builder.run(goal=refined_goal, plan=plan)
    save(run_dir, "02_builder_draft_v0.txt", draft)
    print(f"    Draft length : {len(draft)} chars")

    # ── IMPROVEMENT LOOP ──────────────────────────────────────────────────────
    best_draft = draft
    best_score = 0
    previous_score = 0
    stop_reason = "max_loops"

    critic = CriticAgent(model=model_fast)
    fixer = FixerAgent(model=model_main)
    judge = JudgeAgent(model=model_main, pass_threshold=threshold)

    for iteration in range(1, max_loops + 1):
        summary["iterations_run"] = iteration

        header(f"LOOP {iteration}/{max_loops}", "CRITIC → FIXER → JUDGE")

        # Critic
        print(f"  [Critic] Reviewing draft (iteration {iteration})...")
        critique = critic.run(goal=refined_goal, draft=draft)
        save(run_dir, f"loop{iteration:02d}_critic.txt", critique)

        # Fixer
        revised = fixer.run(
            goal=refined_goal, draft=draft,
            critique=critique, iteration=iteration
        )
        save(run_dir, f"loop{iteration:02d}_fixer.txt", revised)

        # Judge
        verdict = judge.run(goal=refined_goal, draft=revised, iteration=iteration)
        save(run_dir, f"loop{iteration:02d}_judge.json", json.dumps(verdict, indent=2))

        score = verdict["total_score"]
        summary["scores"].append(score)
        print(f"    Score: {score_bar(score)}")

        # Track best
        if score > best_score:
            best_score = score
            best_draft = revised
            save(run_dir, "best_draft.txt", best_draft)

        # Stop conditions
        if verdict["pass"]:
            stop_reason = f"passed (score {score} >= threshold {threshold})"
            draft = revised
            break

        if iteration > 1:
            improvement = score - previous_score
            if improvement < min_improvement:
                stop_reason = (
                    f"stalled (improvement {improvement} < "
                    f"min_improvement {min_improvement})"
                )
                draft = revised
                break

        if verdict.get("hard_fails"):
            stop_reason = f"hard_fail: {verdict['hard_fails']}"
            draft = revised
            break

        previous_score = score
        draft = revised

    else:
        stop_reason = f"max_loops ({max_loops}) reached"

    # ── FINAL SYNTHESIZER ─────────────────────────────────────────────────────
    header("FINAL", "SYNTHESIZER — Polish best draft")
    synthesizer = SynthesizerAgent(model=model_main)
    final_output = synthesizer.run(
        goal=refined_goal,
        best_draft=best_draft,
        score=best_score,
        iterations=summary["iterations_run"],
    )
    save(run_dir, "final_output.txt", final_output)

    summary["stop_reason"] = stop_reason
    summary["final_score"] = best_score
    summary["passed"] = best_score >= threshold
    save(run_dir, "run_summary.json", json.dumps(summary, indent=2))

    return summary, final_output


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Local AI Orchestrator — full terminal pipeline"
    )

    parser.add_argument("--goal", required=True,
                        help="The goal or task for the pipeline.")
    parser.add_argument("--model-main", default=DEFAULT_MODEL_MAIN,
                        help=f"Main model (Builder/Fixer/Judge). Default: {DEFAULT_MODEL_MAIN}")
    parser.add_argument("--model-fast", default=DEFAULT_MODEL_FAST,
                        help=f"Fast model (Supervisor/Planner/Critic). Default: {DEFAULT_MODEL_FAST}")
    parser.add_argument("--max-loops", type=int, default=DEFAULT_MAX_LOOPS,
                        help=f"Max improvement loops. Default: {DEFAULT_MAX_LOOPS}")
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD,
                        help=f"Pass score (0–100). Default: {DEFAULT_THRESHOLD}")
    parser.add_argument("--min-improvement", type=int, default=DEFAULT_MIN_IMPROVEMENT,
                        help=f"Min score gain per loop before stopping. Default: {DEFAULT_MIN_IMPROVEMENT}")
    args = parser.parse_args()

    run_dir = make_run_dir()

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║         LOCAL AI ORCHESTRATOR — TERMINAL MVP            ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  Goal        : {args.goal[:70]}")
    print(f"  Main model  : {args.model_main}")
    print(f"  Fast model  : {args.model_fast}")
    print(f"  Max loops   : {args.max_loops}")
    print(f"  Threshold   : {args.threshold}/100")
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
        )
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Run stopped by user.")
        print(f"Partial output saved to: {run_dir}/")
        sys.exit(0)

    elapsed = (datetime.now() - start).seconds

    # ── FINAL OUTPUT ──────────────────────────────────────────────────────────
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                    FINAL OUTPUT                         ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    print(final_output)

    # ── RUN SUMMARY ───────────────────────────────────────────────────────────
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                    RUN SUMMARY                          ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  Stop reason   : {summary['stop_reason']}")
    print(f"  Final score   : {score_bar(summary['final_score'])}")
    print(f"  Passed        : {'YES ✓' if summary['passed'] else 'NO ✗'}")
    print(f"  Loops run     : {summary['iterations_run']} / {args.max_loops}")

    if summary["scores"]:
        score_history = " → ".join(str(s) for s in summary["scores"])
        print(f"  Score history : {score_history}")

    print(f"  Time elapsed  : {elapsed}s")
    print(f"  Run saved to  : {run_dir}/")
    print()


if __name__ == "__main__":
    main()
