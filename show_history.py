"""
show_history.py

Display recent run history from the SQLite database.

Usage:
    python show_history.py
    python show_history.py --run-id 3
    python show_history.py --stats
"""

import argparse
from orchestrator.database import (
    load_all_runs,
    load_run_by_id,
    get_db_stats,
    reset_database,
)


def main():
    parser = argparse.ArgumentParser(description="View Local AI Orchestrator run history")
    parser.add_argument("--run-id", type=int, help="Show details for a specific run ID")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    parser.add_argument("--reset", action="store_true",
                        help="⚠️ Delete ALL run history from the database")
    parser.add_argument("--limit", type=int, default=20,
                        help="Number of recent runs to show (default: 20)")
    args = parser.parse_args()

    if args.reset:
        confirm = input("⚠️  This will delete ALL run history. Type 'yes' to confirm: ")
        if confirm.strip().lower() == "yes":
            reset_database()
            print("Database reset. All run history deleted.")
        else:
            print("Reset cancelled.")
        return

    if args.stats:
        stats = get_db_stats()
        print("\nDatabase statistics:")
        print(f"  Total runs   : {stats['total_runs']}")
        print(f"  Passed runs  : {stats['passed_runs']}")
        print(f"  Average score: {stats['average_score']}/100")
        return

    if args.run_id:
        run = load_run_by_id(args.run_id)
        if run is None:
            print(f"No run found with ID {args.run_id}")
            return

        print(f"\n{'=' * 60}")
        print(f"  Run #{run['id']} — {run['timestamp']}")
        print(f"{'=' * 60}")
        print(f"  Goal         : {run['goal']}")
        print(f"  Refined goal : {run['refined_goal']}")
        print(f"  Mode         : {run['mode']}")
        print(f"  Model (main) : {run['model_main']}")
        print(f"  Model (fast) : {run['model_fast']}")
        print(f"  Final score  : {run['final_score']}/100")
        print(f"  Passed       : {'Yes' if run['passed'] else 'No'}")
        print(f"  Stop reason  : {run['stop_reason']}")
        print(f"  Scores       : {run['scores_list']}")
        print(f"  Run dir      : {run['run_dir']}")
        print()

        for it in run.get("iterations_detail", []):
            print(f"  --- Iteration {it['iteration']} (score: {it['score']}/100) ---")
            print(f"  Critique preview: {it['critique'][:200]}.")
            print()

        print("FINAL OUTPUT:")
        print(run.get("final_output", "[not stored]"))
        return

    runs = load_all_runs(limit=args.limit)
    if not runs:
        print("\nNo runs found in the database yet.")
        print("Run the pipeline with: python run.py --goal '...'")
        return

    print(f"\n{'ID':<5} {'Timestamp':<20} {'Score':<8} {'Pass':<6} "
          f"{'Loops':<6} {'Mode':<10} Goal")
    print("-" * 80)
    for run in runs:
        goal_preview = run["goal"][:35] + ("..." if len(run["goal"]) > 35 else "")
        passed_str = "✓" if run["passed"] else "✗"
        print(
            f"{run['id']:<5} {run['timestamp'][:19]:<20} "
            f"{run['final_score']:<8} {passed_str:<6} "
            f"{run['iterations']:<6} {run['mode']:<10} {goal_preview}"
        )

    print()
    print(f"  Showing {len(runs)} most recent runs.")
    print("  Use --run-id <ID> to see full details for a specific run.")


if __name__ == "__main__":
    main()
