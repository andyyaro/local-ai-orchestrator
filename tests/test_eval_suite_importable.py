"""
tests/test_eval_suite_importable.py

Phase 12: eval/ scenarios call real models and real (mocked, where noted)
external boundaries, so they don't belong in the CI-run tests/ suite --
see eval/run_eval_suite.py, a human-run acceptance step. This is a
minimal CI-safe check that eval.scenarios itself is at least importable
and doesn't crash on a missing phase, so a typo in an import path is
still caught automatically.
"""


def test_eval_suite_imports():
    import eval.scenarios  # noqa: F401


def test_eval_suite_has_all_scenarios_listed():
    import eval.scenarios as scenarios

    assert len(scenarios.ALL_SCENARIOS) >= 10
    assert all(callable(fn) for fn in scenarios.ALL_SCENARIOS)
