"""
run_langgraph.py

Run the LangGraph version of the pipeline.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from orchestrator.config_loader import get_active_profile
from orchestrator.graph import build_graph


RUNS_DIR = Path("runs")
DEFAULT_MAX_LOOPS = 3
DEFAULT_THRESHOLD = 70
DEFAULT_MIN_IMPROVEMENT = 5


def make_run_dir() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RUNS_DIR / f"lg_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def score_bar(score: int, width: int = 40) -> str:
    filled = int(score / 100 * width)
    return f"[{'█' * filled}{'░' * (width - filled)}] {score}/100"


def main():
    parser = argparse.ArgumentParser(
        description="LangGraph pipeline for the Local AI Orchestrator"
    )
    parser.add_argument("--goal", required=True)
    parser.add_argument("--model-main", default=None,
                        help="Optional override for Builder/Fixer/Judge/Synthesizer.")
    parser.add_argument("--model-fast", default=None,
                        help="Optional override for Supervisor/Planner/Critic.")
    parser.add_argument("--max-loops", type=int, default=DEFAULT_MAX_LOOPS)
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD)
    parser.add_argument("--min-improvement", type=int, default=DEFAULT_MIN_IMPROVEMENT)
    args = parser.parse_args()

    run_dir = make_run_dir()
    active_profile = get_active_profile()

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║      LOCAL AI ORCHESTRATOR — LANGGRAPH PIPELINE         ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  Goal       : {args.goal[:70]}")
    print(f"  Profile    : {active_profile}")
    print(f"  Main model : {args.model_main or 'config-driven'}")
    print(f"  Fast model : {args.model_fast or 'config-driven'}")
    print(f"  Run dir    : {run_dir}")

    initial_state = {
        "goal": args.goal,
        "model_main": args.model_main,
        "model_fast": args.model_fast,
        "max_loops": args.max_loops,
        "threshold": args.threshold,
        "min_improvement": args.min_improvement,
        "run_dir": str(run_dir),
    }

    app = build_graph()
    start = datetime.now()

    try:
        step_output = None
        for step_output in app.stream(initial_state, stream_mode="values"):
            if "final_output" in step_output:
                pass
            elif "verdict" in step_output and step_output.get("scores"):
                scores = step_output["scores"]
                latest = scores[-1]
                print(f"\n  Loop {len(scores)} score: {score_bar(latest)}")

        final_state = step_output or {}

    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Run stopped by user.")
        print(f"Partial output saved to: {run_dir}/")
        sys.exit(0)

    elapsed = (datetime.now() - start).seconds

    final_output = final_state.get("final_output", "[No output produced]")
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                    FINAL OUTPUT                         ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    print(final_output)

    scores = final_state.get("scores", [])
    best_score = final_state.get("best_score", 0)
    stop_reason = final_state.get("stop_reason", "unknown")
    passed = best_score >= args.threshold

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                    RUN SUMMARY                          ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  Stop reason   : {stop_reason}")
    print(f"  Final score   : {score_bar(best_score)}")
    print(f"  Passed        : {'YES ✓' if passed else 'NO ✗'}")
    print(f"  Loops run     : {len(scores)} / {args.max_loops}")
    if scores:
        print(f"  Score history : {' → '.join(str(s) for s in scores)}")
    print(f"  Time elapsed  : {elapsed}s")
    print(f"  Run saved to  : {run_dir}/")
    print()


if __name__ == "__main__":
    main()
