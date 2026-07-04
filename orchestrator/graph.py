"""
orchestrator/graph.py

LangGraph pipeline for the Local AI Orchestrator.
"""

import json
from pathlib import Path
from typing import Literal

from langgraph.graph import StateGraph, END

from memory.embeddings import EmbeddingModelUnavailableError
from memory.retriever import retrieve_context
from orchestrator.state import PipelineState
from orchestrator.config_loader import get_memory_config, get_model_for_role, get_num_ctx_for_profile
from orchestrator.router import classify_path, get_path_config
from orchestrator.validators import (
    run_validators,
    apply_validator_results_to_verdict,
    should_break_on_hard_fail,
)
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


def _num_ctx() -> int:
    """Context window size for the active profile, so every agent's KV cache
    footprint scales with config/models.yaml's context_sizes rather than a
    single hardcoded default regardless of profile."""
    return get_num_ctx_for_profile()


def node_supervisor(state: PipelineState) -> dict:
    agent = SupervisorAgent(model=_role_model(state, "supervisor"), num_ctx=_num_ctx())
    result = agent.run(goal=state["goal"])
    _save(state["run_dir"], "00_supervisor.json", json.dumps(result, indent=2))

    refined_goal = result["refined_goal"]
    mode = result["mode"]
    path = classify_path(refined_goal, mode, override=state.get("path_override"))
    path_config = get_path_config(path)

    # Phase 9: optional retrieval over prior run history and project
    # files, off by default (memory.retrieval_enabled). Never blocks the
    # pipeline if the embedding model isn't pulled -- retrieval is an
    # opt-in enhancement, not a hard requirement to produce output.
    retrieved_context = ""
    if get_memory_config().get("retrieval_enabled", False):
        try:
            retrieved_context = retrieve_context(refined_goal)
        except EmbeddingModelUnavailableError:
            retrieved_context = ""
    augmented_goal = f"{retrieved_context}\n\n{refined_goal}" if retrieved_context else refined_goal

    return {
        "refined_goal": refined_goal,
        "augmented_goal": augmented_goal,
        "mode": mode,
        "path": path,
        "skip_planner": path_config["skip_planner"],
        "skip_critic_fixer_loop": path_config["skip_critic_fixer_loop"],
        "max_loops": state.get("max_loops") or path_config["max_loops"],
        "threshold": state.get("threshold") or path_config["threshold"],
    }


def node_planner(state: PipelineState) -> dict:
    agent = PlannerAgent(model=_role_model(state, "planner"), num_ctx=_num_ctx())
    plan = agent.run(goal=state.get("augmented_goal") or state["refined_goal"], mode=state["mode"])
    _save(state["run_dir"], "01_planner_plan.txt", plan)
    return {"plan": plan}


def node_builder(state: PipelineState) -> dict:
    # Fast path skips node_planner entirely, so no "plan" key is set yet —
    # fall back to the refined goal, matching run.py's fast-path wiring.
    plan = state.get("plan") or state["refined_goal"]
    agent = BuilderAgent(model=_role_model(state, "builder"), num_ctx=_num_ctx())
    draft = agent.run(
        goal=state.get("augmented_goal") or state["refined_goal"],
        plan=plan,
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
    agent = CriticAgent(model=_role_model(state, "critic"), num_ctx=_num_ctx())
    critique = agent.run(goal=state["refined_goal"], draft=state["draft"])

    previous_validator_feedback = state.get("previous_validator_feedback", "")
    if previous_validator_feedback:
        critique += (
            "\n\nDETERMINISTIC CONSTRAINT FEEDBACK FROM PREVIOUS REVISION:\n"
            f"{previous_validator_feedback}\n"
            "The next revision MUST satisfy this constraint exactly (for "
            "example, hitting a required word count), even if it means "
            "shortening or restructuring the draft."
        )

    _save(state["run_dir"], f"loop{iteration:02d}_critic.txt", critique)
    return {"critique": critique}


def node_fixer(state: PipelineState) -> dict:
    iteration = state.get("iteration", 1)
    agent = FixerAgent(model=_role_model(state, "fixer"), num_ctx=_num_ctx())
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

    # Fast path skips node_critic/node_fixer, so no "revised" key is set yet —
    # fall back to the builder's draft, matching run.py's fast-path wiring.
    revised = state.get("revised") or state["draft"]

    validator_results = run_validators(
        state["refined_goal"], revised, mode, original_goal=state["goal"]
    )
    _save(
        state["run_dir"],
        f"loop{iteration:02d}_validators.json",
        json.dumps([r.__dict__ for r in validator_results], indent=2),
    )

    agent = JudgeAgent(model=_role_model(state, "judge"), pass_threshold=threshold, num_ctx=_num_ctx())
    verdict = agent.run(
        goal=state["refined_goal"],
        draft=revised,
        iteration=iteration,
        mode=mode,
    )
    verdict = apply_validator_results_to_verdict(verdict, validator_results)
    _save(state["run_dir"], f"loop{iteration:02d}_judge.json",
          json.dumps(verdict, indent=2))

    score = verdict["total_score"]
    scores = state.get("scores", []) + [score]

    best_score = state.get("best_score", 0)
    best_draft = state.get("best_draft", revised)
    if score > best_score:
        best_score = score
        best_draft = revised
        _save(state["run_dir"], "best_draft.txt", best_draft)

    max_loops = state.get("max_loops", 3)
    min_improvement = state.get("min_improvement", 5)
    previous_score = state.get("previous_score", 0)
    skip_critic_fixer_loop = state.get("skip_critic_fixer_loop", False)
    should_continue = True
    stop_reason = ""

    # The fast path's single no-critic/fixer pass is only "fast" on the
    # very first judge call (iteration 1). If that pass hard-fails on a
    # repairable constraint_violation, this behaves like the normal path
    # from here on -- falling back into the same critic/fixer/judge cycle
    # for the remaining iterations instead of failing immediately, since
    # the fast path skipping Critic/Fixer shouldn't mean skipping repair.
    fast_first_pass = skip_critic_fixer_loop and iteration == 1

    if verdict["pass"]:
        should_continue = False
        stop_reason = f"passed (score {score} >= threshold {threshold})"
    elif fast_first_pass and should_break_on_hard_fail(mode, verdict, iteration, max_loops):
        should_continue = False
        stop_reason = (
            f"hard_fail: {verdict['hard_fails']}" if verdict.get("hard_fails")
            else f"fast path single iteration complete (score {score})"
        )
    elif fast_first_pass:
        should_continue = True
        stop_reason = ""
    elif iteration >= max_loops:
        should_continue = False
        stop_reason = f"max_loops ({max_loops}) reached"
    elif verdict.get("hard_fails") and should_break_on_hard_fail(mode, verdict, iteration, max_loops):
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

    failed_validators = [r for r in validator_results if not r.passed]
    validator_feedback = "; ".join(r.detail for r in failed_validators)

    return {
        "verdict": verdict,
        "scores": scores,
        "best_score": best_score,
        "best_draft": best_draft,
        "previous_score": score,
        "previous_validator_feedback": validator_feedback,
        "draft": revised,
        "iteration": iteration + 1,
        "should_continue": should_continue,
        "stop_reason": stop_reason,
    }


def node_synthesizer(state: PipelineState) -> dict:
    agent = SynthesizerAgent(model=_role_model(state, "synthesizer"), num_ctx=_num_ctx())
    mode = state.get("mode", "general")
    final = agent.run(
        goal=state["goal"],
        best_draft=state["best_draft"],
        score=state["best_score"],
        iterations=state.get("iteration", 1) - 1,
    )

    final_validator_results = run_validators(state["goal"], final, mode)
    _save(
        state["run_dir"],
        "final_validators.json",
        json.dumps([r.__dict__ for r in final_validator_results], indent=2),
    )
    final_failed = [r for r in final_validator_results if not r.passed]
    if final_failed:
        # The Synthesizer expanded an already-validated draft into an
        # invalid final answer -- do not ship it. Fall back to the
        # pre-synthesis best_draft, which already passed constraint
        # validation in node_judge.
        final = state["best_draft"]
    _save(state["run_dir"], "final_output.txt", final)

    summary = {
        "goal": state["goal"],
        "refined_goal": state["refined_goal"],
        "mode": state.get("mode", "general"),
        "path": state.get("path", "normal"),
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


def route_after_supervisor(state: PipelineState) -> Literal["planner", "builder"]:
    if state.get("skip_planner", False):
        return "builder"
    return "planner"


def route_after_builder(state: PipelineState) -> Literal["critic", "judge"]:
    if state.get("skip_critic_fixer_loop", False):
        return "judge"
    return "critic"


def route_after_judge(state: PipelineState) -> Literal["critic", "synthesizer"]:
    # skip_critic_fixer_loop no longer forces "synthesizer" unconditionally:
    # node_judge sets should_continue=True on the fast path's first pass
    # when it hard-fails on a repairable constraint_violation, so this must
    # still be able to route into critic/fixer for the repair attempt.
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

    graph.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {"planner": "planner", "builder": "builder"},
    )
    graph.add_edge("planner", "builder")

    graph.add_conditional_edges(
        "builder",
        route_after_builder,
        {"critic": "critic", "judge": "judge"},
    )
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
