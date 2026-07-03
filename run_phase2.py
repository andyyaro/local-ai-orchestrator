"""
run_phase2.py

Phase 2: Two-agent terminal pipeline.
Builder writes a draft. Critic reviews it.
Outputs are saved to runs/<timestamp>/.

Usage:
    python run_phase2.py --goal "Your goal here"
    python run_phase2.py --goal "Your goal here" --model llama3.2:3b
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from agents.builder import BuilderAgent
from agents.critic import CriticAgent


DEFAULT_MODEL_FAST = "llama3.2:3b"
DEFAULT_MODEL_MAIN = "llama3.2:3b"   # Bootstrap default — upgrade via config/models.yaml
RUNS_DIR = Path("runs")


def make_run_dir() -> Path:
    """Create a timestamped directory for this run's output files."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RUNS_DIR / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def save_file(run_dir: Path, filename: str, content: str):
    """Write content to a file inside the run directory."""
    filepath = run_dir / filename
    filepath.write_text(content, encoding="utf-8")
    print(f"  [Saved] {filepath}")


def print_separator(label: str):
    width = 60
    print()
    print("=" * width)
    print(f"  {label}")
    print("=" * width)


def main():
    parser = argparse.ArgumentParser(
        description="Phase 2: Builder → Critic terminal pipeline"
    )
    parser.add_argument(
        "--goal", required=True,
        help="The goal or task you want the pipeline to work on."
    )
    parser.add_argument(
        "--model-main", default=DEFAULT_MODEL_MAIN,
        help=f"Model for Builder (default: {DEFAULT_MODEL_MAIN})"
    )
    parser.add_argument(
        "--model-fast", default=DEFAULT_MODEL_FAST,
        help=f"Model for Critic (default: {DEFAULT_MODEL_FAST})"
    )
    args = parser.parse_args()

    goal = args.goal.strip()
    run_dir = make_run_dir()

    print()
    print("LOCAL AI ORCHESTRATOR — Phase 2: Builder → Critic")
    print(f"Run directory : {run_dir}")
    print(f"Goal          : {goal}")
    print(f"Builder model : {args.model_main}")
    print(f"Critic model  : {args.model_fast}")

    # ── STEP 1: BUILDER ──────────────────────────────────────────────────────
    print_separator("STEP 1 of 2: BUILDER")
    print("  The Builder will write a full draft based on your goal.")
    print()

    # For Phase 2, pass the goal directly as the plan (no Planner yet)
    plan_stub = f"Write a thorough, well-structured response to this goal:\n{goal}"

    builder = BuilderAgent(model=args.model_main)
    draft = builder.run(goal=goal, plan=plan_stub)

    save_file(run_dir, "01_builder_draft.txt", draft)

    print()
    print("BUILDER OUTPUT:")
    print("-" * 60)
    print(draft)

    # ── STEP 2: CRITIC ───────────────────────────────────────────────────────
    print_separator("STEP 2 of 2: CRITIC")
    print("  The Critic will review the draft against your original goal.")
    print()

    critic = CriticAgent(model=args.model_fast)
    critique = critic.run(goal=goal, draft=draft)

    save_file(run_dir, "02_critic_review.txt", critique)

    # Save run metadata
    metadata = {
        "goal": goal,
        "builder_model": args.model_main,
        "critic_model": args.model_fast,
        "run_dir": str(run_dir),
        "draft_length": len(draft),
        "critique_length": len(critique),
    }
    save_file(run_dir, "metadata.json", json.dumps(metadata, indent=2))

    print()
    print("CRITIC OUTPUT:")
    print("-" * 60)
    print(critique)

    # ── SUMMARY ──────────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  RUN COMPLETE")
    print("=" * 60)
    print(f"  Run saved to : {run_dir}/")
    print(f"  Files saved  :")
    print(f"    01_builder_draft.txt  ({len(draft)} chars)")
    print(f"    02_critic_review.txt  ({len(critique)} chars)")
    print(f"    metadata.json")
    print()
    print("  Next step: Review the critique in the run directory.")
    print("  If the critique is useful, proceed to Phase 3 (Fixer + Judge).")


if __name__ == "__main__":
    main()
