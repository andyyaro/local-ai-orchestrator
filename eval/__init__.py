"""
eval/

Phase 12: the final end-to-end eval suite. This is a human-run
acceptance step, not a CI job -- several scenarios call a real local
model and are too slow/hardware-dependent to run on every push. See
docs/upgrade-guide/17-phase-12-eval-suite-checklist.md.

Run with:
    python eval/run_eval_suite.py
"""
