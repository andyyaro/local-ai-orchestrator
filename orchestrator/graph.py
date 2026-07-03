"""
orchestrator/graph.py

LangGraph pipeline for the Local AI Orchestrator.

Graph structure:
  supervisor → planner → builder → critic → fixer → judge → router
                                      ↑___________________________|
                                      (if should_continue is True)
                                                    ↓
                                             (if False) synthesizer → END
"""

import json
from pathlib import Path
from typing import Literal

from langgraph.graph import StateGraph, END

from orchestrator.state import PipelineState
from agents.supervisor import SupervisorAgent
from agents.planner import PlannerAgent
from agents.builder import BuilderAgent
from agents.critic import CriticAgent
from agents.fixer import FixerAgent
from agents.judge import JudgeAgent
from agents.synthesizer import SynthesizerAgent


# ── File saving helper ────────────────────────────────────────────────────────

def _save(run_dir: str, filename: str, content: str):
    path = Path(run_dir) / filename
    path.write_text(content, encoding="utf-8")


# ── Node functions ────────────────────────────────────────────────────────────
# Each node receives the full state dict and returns a partial dict
# containing only the keys it wants to update.

def node_supervisor(state: PipelineState) -> dict:
    agent = SupervisorAgent(model=state["model_fast"])
    result = agent.run(goal=state["goal"])
    _save(state["run_dir"], "00_supervisor.json", json.dumps(result, indent=2))
    return {
        "refined_goal": result["refined_goal"],
        "mode": result["mode"],
    }


def node_planner(state: PipelineState) -> dict:
    agent = PlannerAgent(model=state["model_fast"])
    plan = agent.run(goal=state["refined_goal"], mode=state["mode"])
    _save(state["run_dir"], "01_planner_plan.txt", plan)
    return {"plan": plan}


def node_builder(state: PipelineState) -> dict:
    agent = BuilderAgent(model=state["model_main"])
    draft = agent.run(goal=state["refined_goal"], plan=state["plan"])
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
    agent = CriticAgent(model=state["model_fast"])
    critique = agent.run(goal=state["refined_goal"], draft=state["draft"])
    _save(state["run_dir"], f"loop{iteration:02d}_critic.txt", critique)
    return {"critique": critique}


def node_fixer(state: PipelineState) -> dict:
    iteration = state.get("iteration", 1)
    agent = FixerAgent(model=state["model_main"])
    revised = agent.run(
        goal=state["refined_goal"],
        draft=state["draft"],
        critique=state["critique"],
        iteration=iteration,
    )
    _save(state["run_dir"], f"loop{iteration:02d}_fixer.txt", revised)
    return {"revised": revised}


def node_judge(state: PipelineState) -> dict:
    iteration = state.get("iteration", 1)
    threshold = state.get("threshold", 70)

    agent = JudgeAgent(model=state["model_main"], pass_threshold=threshold)
    verdict = agent.run(
        goal=state["refined_goal"],
        draft=state["revised"],
        iteration=iteration,
    )
    _save(state["run_dir"], f"loop{iteration:02d}_judge.json",
          json.dumps(verdict, indent=2))

    score = verdict["total_score"]
    scores = state.get("scores", []) + [score]

    # Track best draft
    best_score = state.get("best_score", 0)
    best_draft = state.get("best_draft", state["revised"])
    if score > best_score:
        best_score = score
        best_draft = state["revised"]
        _save(state["run_dir"], "best_draft.txt", best_draft)

    # Determine whether to continue
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
        "draft": state["revised"],       # feed revision forward as new draft
        "iteration": iteration + 1,
        "should_continue": should_continue,
        "stop_reason": stop_reason,
    }


def node_synthesizer(state: PipelineState) -> dict:
    agent = SynthesizerAgent(model=state["model_main"])
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
        "model_main": state["model_main"],
        "model_fast": state["model_fast"],
        "iterations_run": state.get("iteration", 1) - 1,
        "scores": state.get("scores", []),
        "best_score": state["best_score"],
        "threshold": state.get("threshold", 70),
        "stop_reason": state.get("stop_reason", ""),
        "passed": state["best_score"] >= state.get("threshold", 70),
    }
    _save(state["run_dir"], "run_summary.json", json.dumps(summary, indent=2))

    return {"final_output": final}


# ── Routing function ──────────────────────────────────────────────────────────

def route_after_judge(state: PipelineState) -> Literal["critic", "synthesizer"]:
    """
    Conditional edge: after Judge, decide whether to loop back to Critic
    or proceed to the Synthesizer.
    """
    if state.get("should_continue", False):
        return "critic"
    return "synthesizer"


# ── Build the graph ───────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(PipelineState)

    # Add nodes
    graph.add_node("supervisor", node_supervisor)
    graph.add_node("planner", node_planner)
    graph.add_node("builder", node_builder)
    graph.add_node("critic", node_critic)
    graph.add_node("fixer", node_fixer)
    graph.add_node("judge", node_judge)
    graph.add_node("synthesizer", node_synthesizer)

    # Add unconditional edges (always proceed to next node)
    graph.add_edge("supervisor", "planner")
    graph.add_edge("planner", "builder")
    graph.add_edge("builder", "critic")
    graph.add_edge("critic", "fixer")
    graph.add_edge("fixer", "judge")

    # Conditional edge after Judge
    graph.add_conditional_edges(
        "judge",
        route_after_judge,
        {
            "critic": "critic",           # loop back
            "synthesizer": "synthesizer", # proceed to finish
        },
    )

    graph.add_edge("synthesizer", END)

    # Set entry point
    graph.set_entry_point("supervisor")

    return graph.compile()
