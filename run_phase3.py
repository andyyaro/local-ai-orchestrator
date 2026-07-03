"""
run_phase3.py

Phase 3: Four-agent terminal pipeline.
Builder → Critic → Fixer → Judge

Outputs are saved to runs/<timestamp>/.
The Judge returns structured JSON with scores and a pass/fail verdict.

Usage:
    python run_phase3.py --goal "Your goal here"
    python run_phase3.py --goal "Your goal here" --threshold 75
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from agents.builder import BuilderAgent
from agents.critic import CriticAgent
from agents.fixer import FixerAgent
from agents.judge import JudgeAgent


DEFAULT_MODEL_MAIN = "llama3.2:3b"   # Bootstrap default; override with --model-main
DEFAULT_MODEL_FAST = "llama3.2:3b"
DEFAULT_THRESHOLD = 70
RUNS_DIR = Path("runs")


def make_run_dir() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RUNS_DIR / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def save(run_dir: Path, filename: str, content: str):
    path = run_dir / filename
    path.write_text(content, encoding="utf-8")
    print(f"  [Saved] {path}")


def header(label: str):
    print()
    print("=" * 60)
    print(f"  {label}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Phase 3: Builder → Critic → Fixer → Judge"
    )
    parser.add_argument("--goal", required=True)
    parser.add_argument("--model-main", default=DEFAULT_MODEL_MAIN)
    parser.add_argument("--model-fast", default=DEFAULT_MODEL_FAST)
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD,
                        help="Minimum score to pass (0–100, default 70)")
    args = parser.parse_args()

    goal = args.goal.strip()
    run_dir = make_run_dir()

    print()
    print("LOCAL AI ORCHESTRATOR — Phase 3: Builder → Critic → Fixer → Judge")
    print(f"Run dir   : {run_dir}")
    print(f"Goal      : {goal}")
    print(f"Threshold : {args.threshold}/100")

    plan_stub = f"Write a thorough, well-structured response to:\n{goal}"

    # ── BUILDER ───────────────────────────────────────────────────────────────
    header("STEP 1 / 4: BUILDER")
    builder = BuilderAgent(model=args.model_main)
    draft = builder.run(goal=goal, plan=plan_stub)
    save(run_dir, "01_builder_draft.txt", draft)
    print("\nDRAFT PREVIEW (first 400 chars):")
    print(draft[:400] + ("..." if len(draft) > 400 else ""))

    # ── CRITIC ────────────────────────────────────────────────────────────────
    header("STEP 2 / 4: CRITIC")
    critic = CriticAgent(model=args.model_fast)
    critique = critic.run(goal=goal, draft=draft)
    save(run_dir, "02_critic_review.txt", critique)
    print("\nCRITIQUE PREVIEW (first 400 chars):")
    print(critique[:400] + ("..." if len(critique) > 400 else ""))

    # ── FIXER ─────────────────────────────────────────────────────────────────
    header("STEP 3 / 4: FIXER")
    fixer = FixerAgent(model=args.model_main)
    revised = fixer.run(goal=goal, draft=draft, critique=critique, iteration=1)
    save(run_dir, "03_fixer_revision_v1.txt", revised)
    print("\nREVISION PREVIEW (first 400 chars):")
    print(revised[:400] + ("..." if len(revised) > 400 else ""))

    # ── JUDGE ─────────────────────────────────────────────────────────────────
    header("STEP 4 / 4: JUDGE")
    judge = JudgeAgent(model=args.model_main, pass_threshold=args.threshold)
    verdict = judge.run(goal=goal, draft=revised, iteration=1)
    save(run_dir, "04_judge_verdict_v1.json", json.dumps(verdict, indent=2))

    # ── SUMMARY ───────────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  VERDICT")
    print("=" * 60)
    print(f"  Total score  : {verdict['total_score']}/100")
    print(f"  Pass/Fail    : {'✓ PASS' if verdict['pass'] else '✗ FAIL'}")
    print(f"  Threshold    : {args.threshold}/100")
    print()
    print("  Category scores:")
    for cat, score in verdict.get("scores", {}).items():
        print(f"    {cat:<16} {score}/25")
    if verdict.get("hard_fails"):
        print(f"\n  Hard fails: {verdict['hard_fails']}")
    print()
    print(f"  Rationale: {verdict.get('rationale', 'N/A')}")
    print()
    print(f"  Run saved to: {run_dir}/")
    print()
    if verdict["pass"]:
        print("  Result: Output passed the quality threshold.")
        print("  Next: Add the reiteration loop (Phase 4).")
    else:
        print(f"  Result: Score {verdict['total_score']} is below threshold {args.threshold}.")
        print("  Next: Add the reiteration loop to auto-improve (Phase 4).")


if __name__ == "__main__":
    main()
