"""
tests/test_pipeline_routing.py

Pipeline-level confirmation of Phase 3 routing: the fast path must skip the
Planner agent entirely (no artifact written) and skip the Critic/Fixer loop
(single Judge check on the Builder's draft instead).
"""

import run as run_module
from agents.builder import BuilderAgent
from agents.critic import CriticAgent
from agents.fixer import FixerAgent
from agents.judge import JudgeAgent
from agents.planner import PlannerAgent
from agents.supervisor import SupervisorAgent
from agents.synthesizer import SynthesizerAgent


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
