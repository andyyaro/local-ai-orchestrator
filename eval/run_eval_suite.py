"""
eval/run_eval_suite.py

Phase 12: runs every scenario in eval/scenarios.py and prints a clear
pass/fail/skipped table. Exits non-zero only if something genuinely
failed -- a skipped scenario (phase not built yet, or a real dependency
like a pulled embedding model isn't available) is expected and fine, and
never counts as a failure.

Run with:
    python eval/run_eval_suite.py
"""

import sys
import time
from pathlib import Path

# Make sure the project root is on sys.path so `eval` resolves as a
# package when this file is run directly (`python eval/run_eval_suite.py`)
# rather than as a module (`python -m eval.run_eval_suite`).
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from eval.scenarios import ALL_SCENARIOS  # noqa: E402


def main() -> int:
    results = []
    print("=" * 78)
    print("LOCAL AI ORCHESTRATOR — PHASE 12 EVAL SUITE")
    print("=" * 78)

    for scenario_fn in ALL_SCENARIOS:
        name = scenario_fn.__name__
        print(f"\n  Running {name} ...")
        start = time.time()
        try:
            result = scenario_fn()
        except Exception as exc:  # pragma: no cover - defensive: a scenario itself must never crash the runner
            from eval.scenarios import EvalResult
            result = EvalResult(name, "fail", f"Scenario raised an unhandled exception: {exc}")
        elapsed = time.time() - start
        results.append((result, elapsed))

        marker = {"pass": "PASS", "fail": "FAIL", "skipped": "SKIP"}.get(result.status, "????")
        print(f"    [{marker}] ({elapsed:.1f}s) {result.message}")

    print("\n" + "=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print(f"  {'Scenario':<45} {'Status':<8} {'Time':>8}")
    print(f"  {'-' * 45} {'-' * 8} {'-' * 8}")
    for result, elapsed in results:
        print(f"  {result.name:<45} {result.status.upper():<8} {elapsed:>6.1f}s")

    passed = sum(1 for r, _ in results if r.status == "pass")
    failed = sum(1 for r, _ in results if r.status == "fail")
    skipped = sum(1 for r, _ in results if r.status == "skipped")
    print(f"\n  {passed} passed, {failed} failed, {skipped} skipped "
          f"(out of {len(results)} scenarios)")

    if failed:
        print("\n  FAILED scenarios:")
        for result, _ in results:
            if result.status == "fail":
                print(f"    - {result.name}: {result.message}")
        return 1

    print("\n  No genuine failures. Skips are expected for phases not yet "
          "built or real dependencies (e.g. a pulled embedding model) not "
          "available in this environment.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
