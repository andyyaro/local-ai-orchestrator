"""Command-line entry point for the Local AI Orchestrator.

This file will become the terminal MVP entry point. The first implementation milestone
is a single local Ollama call; later milestones will connect the full agent pipeline.
"""

from __future__ import annotations

import argparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Local AI Orchestrator MVP.")
    parser.add_argument("--goal", required=False, default="Explain recursion.", help="User goal to send through the orchestrator.")
    parser.add_argument("--mode", required=False, default="planning", help="Workflow mode, such as writing, coding, planning, debugging, or study.")
    parser.add_argument("--profile", required=False, default="bootstrap", help="Model profile to use, such as bootstrap, fast, serious, or coding.")
    parser.add_argument("--max-loops", type=int, default=1, help="Maximum improvement loops to run.")
    parser.add_argument("--threshold", type=int, default=40, help="Judge score threshold for passing.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print("Local AI Orchestrator scaffold is ready.")
    print(f"Goal: {args.goal}")
    print(f"Mode: {args.mode}")
    print(f"Profile: {args.profile}")
    print(f"Max loops: {args.max_loops}")
    print(f"Threshold: {args.threshold}")
    print("Next implementation step: connect the first local Ollama model call.")


if __name__ == "__main__":
    main()
