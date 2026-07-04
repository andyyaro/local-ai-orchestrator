"""
orchestrator/graph.py

LangGraph pipeline for the Local AI Orchestrator.
"""

import json
from pathlib import Path
from typing import Literal

from langgraph.graph import StateGraph, END

from orchestrator.state import PipelineState
from orchestrator.config_loader import get_model_for_role
from orchestrator.validators import run_validators, apply_validator_results_to_verdict
from agents.supervisor import SupervisorAgent
from agents.planner import PlannerAgent
from agents.builder import BuilderAgent
from agents.critic import CriticAgent
from agents.fixer import FixerAgent
from agents.judge import JudgeAgent
from agents.synthesizer import SynthesizerAgent


def _save(run_dir: str, filename: str, content: str):
    path = Path(run_dir) / filename
    path.write_text(content, encoding="utf-8")


def _role_model(state: PipelineState, role: str) -> str:
    mode = state.get("mode", "general")
    model_main = state.get("model_main")
    model_fast = state.get("model_fast")

    if model_fast and role in {"supervisor", "planner", "critic"}:
        return model_fast
    if model_main and role in {"builder", "fixer", "judge", "synthesizer"}:
        return model_main
    return get_model_for_role(role, mode)


def node_supervisor(state: PipelineState) -> dict:
    agent = SupervisorAgent(model=_role_model(state, "supervisor"))
    result = agent.run(goal=state["goal"])
    _save(state["run_dir"], "00_supervisor.json", json.dumps(result, indent=2))
    return {
        "refined_goal": result["refined_goal"],
        "mode": result["mode"],
    }


def node_planner(state: PipelineState) -> dict:
    agent = PlannerAgent(model=_role_model(state, "planner"))
    plan = agent.run(goal=state["refined_goal"], mode=state["mode"])
    _save(state["run_dir"], "01_planner_plan.txt", plan)
    return {"plan": plan}


def node_builder(state: PipelineState) -> dict:
    agent = BuilderAgent(model=_role_model(state, "builder"))
    draft = agent.run(
        goal=state["refined_goal"],
        plan=state["plan"],
        mode=state.get("mode", "general"),
    )
    _save(state["run_dir"], "02_builder_draft_v0.txt", draft)
    return {
        "draft": draft,
        "best_draft": draft,
        "iteration": 1,
        "scores": [],
        "previous_score": 0,
        "best_score": 0,
        "should_continue": True,
        "stop_reason": "",
    }


def node_critic(state: PipelineState) -> dict:
    iteration = state.get("iteration", 1)
    agent = CriticAgent(model=_role_model(state, "critic"))
    critique = agent.run(goal=state["refined_goal"], draft=state["draft"])
    _save(state["run_dir"], f"loop{iteration:02d}_critic.txt", critique)
    return {"critique": critique}


def node_fixer(state: PipelineState) -> dict:
    iteration = state.get("iteration", 1)
    agent = FixerAgent(model=_role_model(state, "fixer"))
    revised = agent.run(
        goal=state["refined_goal"],
        draft=state["draft"],
        critique=state["critique"],
        iteration=iteration,
        mode=state.get("mode", "general"),
    )
    _save(state["run_dir"], f"loop{iteration:02d}_fixer.txt", revised)
    return {"revised": revised}


def node_judge(state: PipelineState) -> dict:
    iteration = state.get("iteration", 1)
    threshold = state.get("threshold", 70)
    mode = state.get("mode", "general")

    validator_results = run_validators(state["refined_goal"], state["revised"], mode)
    _save(
        state["run_dir"],
        f"loop{iteration:02d}_validators.json",
        json.dumps([r.__dict__ for r in validator_results], indent=2),
    )

    agent = JudgeAgent(model=_role_model(state, "judge"), pass_threshold=threshold)
    verdict = agent.run(
        goal=state["refined_goal"],
        draft=state["revised"],
        iteration=iteration,
        mode=mode,
    )
    verdict = apply_validator_results_to_verdict(verdict, validator_results)
    _save(state["run_dir"], f"loop{iteration:02d}_judge.json",
          json.dumps(verdict, indent=2))

    score = verdict["total_score"]
    scores = state.get("scores", []) + [score]

    best_score = state.get("best_score", 0)
    best_draft = state.get("best_draft", state["revised"])
    if score > best_score:
        best_score = score
        best_draft = state["revised"]
        _save(state["run_dir"], "best_draft.txt", best_draft)

    max_loops = state.get("max_loops", 3)
    min_improvement = state.get("min_improvement", 5)
    previous_score = state.get("previous_score", 0)
    should_continue = True
    stop_reason = ""

    if verdict["pass"]:
        should_continue = False
        stop_reason = f"passed (score {score} >= threshold {threshold})"
    elif iteration >= max_loops:
        should_continue = False
        stop_reason = f"max_loops ({max_loops}) reached"
    elif verdict.get("hard_fails"):
        should_continue = False
        stop_reason = f"hard_fail: {verdict['hard_fails']}"
    elif iteration > 1:
        improvement = score - previous_score
        if improvement < min_improvement:
            should_continue = False
            stop_reason = (
                f"stalled (improvement {improvement} < "
                f"min_improvement {min_improvement})"
            )

    return {
        "verdict": verdict,
        "scores": scores,
        "best_score": best_score,
        "best_draft": best_draft,
        "previous_score": score,
        "draft": state["revised"],
        "iteration": iteration + 1,
        "should_continue": should_continue,
        "stop_reason": stop_reason,
    }


def node_synthesizer(state: PipelineState) -> dict:
    agent = SynthesizerAgent(model=_role_model(state, "synthesizer"))
    final = agent.run(
        goal=state["refined_goal"],
        best_draft=state["best_draft"],
        score=state["best_score"],
        iterations=state.get("iteration", 1) - 1,
    )
    _save(state["run_dir"], "final_output.txt", final)

    summary = {
        "goal": state["goal"],
        "refined_goal": state["refined_goal"],
        "mode": state.get("mode", "general"),
        "model_main_override": state.get("model_main"),
        "model_fast_override": state.get("model_fast"),
        "iterations_run": state.get("iteration", 1) - 1,
        "scores": state.get("scores", []),
        "best_score": state["best_score"],
        "threshold": state.get("threshold", 70),
        "stop_reason": state.get("stop_reason", ""),
        "passed": state["best_score"] >= state.get("threshold", 70),
    }
    _save(state["run_dir"], "run_summary.json", json.dumps(summary, indent=2))

    return {"final_output": final}


def route_after_judge(state: PipelineState) -> Literal["critic", "synthesizer"]:
    if state.get("should_continue", False):
        return "critic"
    return "synthesizer"


def build_graph() -> StateGraph:
    graph = StateGraph(PipelineState)

    graph.add_node("supervisor", node_supervisor)
    graph.add_node("planner", node_planner)
    graph.add_node("builder", node_builder)
    graph.add_node("critic", node_critic)
    graph.add_node("fixer", node_fixer)
    graph.add_node("judge", node_judge)
    graph.add_node("synthesizer", node_synthesizer)

    graph.add_edge("supervisor", "planner")
    graph.add_edge("planner", "builder")
    graph.add_edge("builder", "critic")
    graph.add_edge("critic", "fixer")
    graph.add_edge("fixer", "judge")

    graph.add_conditional_edges(
        "judge",
        route_after_judge,
        {"critic": "critic", "synthesizer": "synthesizer"},
    )

    graph.add_edge("synthesizer", END)
    graph.set_entry_point("supervisor")

    return graph.compile()
