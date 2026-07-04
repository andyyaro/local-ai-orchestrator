"""
tests/test_pipeline_routing.py

Pipeline-level confirmation of Phase 3 routing: the fast path must skip the
Planner agent entirely (no artifact written) and skip the Critic/Fixer loop
(single Judge check on the Builder's draft instead).
"""

import run as run_module
import orchestrator.resilience as resilience
from agents.builder import BuilderAgent
from agents.critic import CriticAgent
from agents.fixer import FixerAgent
from agents.judge import JudgeAgent
from agents.planner import PlannerAgent
from agents.supervisor import SupervisorAgent
from agents.synthesizer import SynthesizerAgent
from orchestrator.resilience import ModelConnectionError


def _fail_if_called(*args, **kwargs):
    raise AssertionError("This agent must not be invoked on the fast path")


def _passing_verdict(self, goal, draft, iteration=1, mode="general"):
    return {
        "scores": {"completeness": 25, "accuracy": 25, "clarity": 25, "usefulness": 25},
        "total_score": 100,
        "pass": True,
        "hard_fails": [],
        "rationale": "Looks good.",
    }


def test_fast_path_skips_planner_and_critic_fixer(tmp_path, monkeypatch):
    monkeypatch.setattr(
        SupervisorAgent, "run",
        lambda self, goal: {
            "refined_goal": "Summarize the water cycle briefly.",
            "mode": "general",
        },
    )
    monkeypatch.setattr(PlannerAgent, "run", _fail_if_called)
    monkeypatch.setattr(
        BuilderAgent, "run",
        lambda self, goal, plan, mode="general": "A short draft about the water cycle.",
    )
    monkeypatch.setattr(CriticAgent, "run", _fail_if_called)
    monkeypatch.setattr(FixerAgent, "run", _fail_if_called)
    monkeypatch.setattr(JudgeAgent, "run", _passing_verdict)
    monkeypatch.setattr(
        SynthesizerAgent, "run",
        lambda self, goal, best_draft, score, iterations: "Final polished output.",
    )
    monkeypatch.setattr(run_module, "save_run", lambda **kwargs: 1)

    run_dir = tmp_path / "run"
    run_dir.mkdir()

    summary, final_output = run_module.run_pipeline(
        goal="Summarize the water cycle briefly.",
        model_main=None,
        model_fast=None,
        max_loops=None,
        threshold=None,
        min_improvement=5,
        run_dir=run_dir,
    )

    assert summary["path"] == "fast"
    assert summary["iterations_run"] == 1
    assert not (run_dir / "01_planner_plan.txt").exists()
    assert final_output == "Final polished output."

    metrics = summary["metrics"]
    assert metrics["path"] == "fast"
    assert "planner" not in metrics["per_agent"]
    assert "critic" not in metrics["per_agent"]
    assert "fixer" not in metrics["per_agent"]
    assert metrics["per_agent"]["judge"]["calls"] == 1


def test_normal_path_runs_planner_and_critic_fixer_loop(tmp_path, monkeypatch):
    monkeypatch.setattr(
        SupervisorAgent, "run",
        lambda self, goal: {
            "refined_goal": (
                "Write a clear explanation of how connection pooling works "
                "in a typical web application backend and why it matters "
                "for latency under load, covering the main tradeoffs teams "
                "usually run into."
            ),
            "mode": "general",
        },
    )
    monkeypatch.setattr(PlannerAgent, "run", lambda self, goal, mode: "1. Explain pooling.")
    monkeypatch.setattr(
        BuilderAgent, "run",
        lambda self, goal, plan, mode="general": "Draft explaining connection pooling.",
    )
    monkeypatch.setattr(CriticAgent, "run", lambda self, goal, draft: "Add more detail.")
    monkeypatch.setattr(
        FixerAgent, "run",
        lambda self, goal, draft, critique, iteration, mode="general": "Revised draft.",
    )
    monkeypatch.setattr(JudgeAgent, "run", _passing_verdict)
    monkeypatch.setattr(
        SynthesizerAgent, "run",
        lambda self, goal, best_draft, score, iterations: "Final polished output.",
    )
    monkeypatch.setattr(run_module, "save_run", lambda **kwargs: 1)

    run_dir = tmp_path / "run"
    run_dir.mkdir()

    summary, final_output = run_module.run_pipeline(
        goal="short goal text",
        model_main=None,
        model_fast=None,
        max_loops=None,
        threshold=None,
        min_improvement=5,
        run_dir=run_dir,
    )

    assert summary["path"] == "normal"
    assert (run_dir / "01_planner_plan.txt").exists()
    assert (run_dir / "loop01_critic.txt").exists()
    assert (run_dir / "loop01_fixer.txt").exists()

    metrics = summary["metrics"]
    assert metrics["path"] == "normal"
    assert metrics["per_agent"]["planner"]["calls"] == 1
    assert metrics["per_agent"]["critic"]["calls"] == 1
    assert metrics["per_agent"]["fixer"]["calls"] == 1
    assert "total_elapsed_ms" in metrics


class _FlakyAdapter:
    """Fails once with a connection error, then succeeds — exercises the
    real BaseAgent.call_model -> call_with_resilience path end to end."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def call(self, model, prompt, temperature, num_ctx, timeout=None):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_pipeline_records_real_resilience_events_in_run_summary(tmp_path, monkeypatch):
    """
    Regression test for the Phase 5b gap: run.py must construct agents with
    the run's RunMetrics instance so that resilience events occurring during
    a real BuilderAgent.call_model() call show up in run_summary.json's
    metrics, instead of always reading 0.
    """
    monkeypatch.setattr(resilience.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        resilience,
        "get_resilience_config",
        lambda: {
            "fallback_model": "llama3.2:3b",
            "max_local_retries": 1,
            "timeouts": {"default": 600, "small": 120, "medium": 300, "large": 600},
        },
    )
    fake_adapter = _FlakyAdapter([
        ModelConnectionError("dropped"),
        "A short draft about the water cycle.",
    ])
    monkeypatch.setattr("orchestrator.adapters.get_adapter", lambda: fake_adapter)

    monkeypatch.setattr(
        SupervisorAgent, "run",
        lambda self, goal: {
            "refined_goal": "Summarize the water cycle briefly.",
            "mode": "general",
        },
    )
    monkeypatch.setattr(PlannerAgent, "run", _fail_if_called)
    # BuilderAgent.run is left un-mocked so its call_model() call really goes
    # through call_with_resilience() with the metrics instance run.py wired in.
    monkeypatch.setattr(CriticAgent, "run", _fail_if_called)
    monkeypatch.setattr(FixerAgent, "run", _fail_if_called)
    monkeypatch.setattr(JudgeAgent, "run", _passing_verdict)
    monkeypatch.setattr(
        SynthesizerAgent, "run",
        lambda self, goal, best_draft, score, iterations: "Final polished output.",
    )
    monkeypatch.setattr(run_module, "save_run", lambda **kwargs: 1)

    run_dir = tmp_path / "run"
    run_dir.mkdir()

    summary, final_output = run_module.run_pipeline(
        goal="Summarize the water cycle briefly.",
        model_main=None,
        model_fast=None,
        max_loops=None,
        threshold=None,
        min_improvement=5,
        run_dir=run_dir,
    )

    assert fake_adapter.calls == 2
    metrics = summary["metrics"]
    assert metrics["retries"] == 1
    assert metrics["fallbacks"] == 0
    assert metrics["timeout_events"] == 0
    assert metrics["per_agent"]["builder"]["calls"] == 1


# ── Phase 6b regression: Supervisor dropping a hard constraint ─────────────────
#
# The exact bug this phase exists to fix: the original user goal said
# "50-word summary," the Supervisor's refined_goal dropped that constraint
# entirely, and because validators previously ran only against refined_goal,
# a 300+ word draft sailed through with a passing Judge score. This test
# reproduces that scenario end to end and asserts the run now honestly
# reports failure instead of silently passing.

def test_pipeline_fails_when_supervisor_drops_original_word_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(
        SupervisorAgent, "run",
        lambda self, goal: {
            "refined_goal": (
                "Explain the physiological and psychological importance of "
                "sleep in humans, with specific examples of how lack of "
                "sleep affects cognitive function."
            ),
            "mode": "writing",
        },
    )
    monkeypatch.setattr(PlannerAgent, "run", _fail_if_called)
    monkeypatch.setattr(
        BuilderAgent, "run",
        lambda self, goal, plan, mode="general": " ".join(["word"] * 300),
    )
    monkeypatch.setattr(CriticAgent, "run", _fail_if_called)
    monkeypatch.setattr(FixerAgent, "run", _fail_if_called)
    monkeypatch.setattr(JudgeAgent, "run", _passing_verdict)
    monkeypatch.setattr(
        SynthesizerAgent, "run",
        lambda self, goal, best_draft, score, iterations: best_draft,
    )
    monkeypatch.setattr(run_module, "save_run", lambda **kwargs: 1)

    run_dir = tmp_path / "run"
    run_dir.mkdir()

    summary, final_output = run_module.run_pipeline(
        goal="Write a 50-word summary of why sleep matters.",
        model_main=None,
        model_fast=None,
        max_loops=None,
        threshold=None,
        min_improvement=5,
        run_dir=run_dir,
    )

    assert summary["passed"] is False
    assert summary["final_score"] == 0
    assert "constraint_violation" in summary["stop_reason"]
    assert summary["metrics"]["hard_fails"].get("constraint_violation") == 1


# ── Phase 6b regression: Synthesizer expanding a valid draft into an invalid one ──

def test_pipeline_reverts_final_output_when_synthesizer_violates_constraint(tmp_path, monkeypatch):
    compliant_draft = " ".join(["word"] * 20)
    bloated_final_output = " ".join(["word"] * 300)

    monkeypatch.setattr(
        SupervisorAgent, "run",
        lambda self, goal: {
            "refined_goal": "Write a summary of the water cycle in exactly 20 words.",
            "mode": "writing",
        },
    )
    monkeypatch.setattr(PlannerAgent, "run", _fail_if_called)
    monkeypatch.setattr(
        BuilderAgent, "run",
        lambda self, goal, plan, mode="general": compliant_draft,
    )
    monkeypatch.setattr(CriticAgent, "run", _fail_if_called)
    monkeypatch.setattr(FixerAgent, "run", _fail_if_called)
    monkeypatch.setattr(JudgeAgent, "run", _passing_verdict)
    monkeypatch.setattr(
        SynthesizerAgent, "run",
        lambda self, goal, best_draft, score, iterations: bloated_final_output,
    )
    monkeypatch.setattr(run_module, "save_run", lambda **kwargs: 1)

    run_dir = tmp_path / "run"
    run_dir.mkdir()

    summary, final_output = run_module.run_pipeline(
        goal="Write a summary of the water cycle in exactly 20 words.",
        model_main=None,
        model_fast=None,
        max_loops=None,
        threshold=None,
        min_improvement=5,
        run_dir=run_dir,
    )

    assert final_output == compliant_draft
    assert (run_dir / "final_output.txt").read_text(encoding="utf-8") == compliant_draft
    assert summary["metrics"]["hard_fails"].get("synthesizer_constraint_violation") == 1
    # The loop itself still succeeded -- only the Synthesizer's output was rejected.
    assert summary["passed"] is True
