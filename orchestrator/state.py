"""
orchestrator/state.py

Defines the shared state object that flows through every node in the
LangGraph pipeline. Every field is optional so nodes can update only
what they produce.
"""

from typing import TypedDict


class PipelineState(TypedDict, total=False):
    # Input
    goal: str                    # user raw goal
    refined_goal: str            # supervisor-cleaned goal
    mode: str                    # writing | coding | planning | debugging | study | general

    # Pipeline data
    plan: str                    # planner numbered plan
    draft: str                   # current working draft updated each loop
    critique: str                # most recent critique
    revised: str                 # most recent fixer output
    verdict: dict                # most recent judge verdict dict

    # Loop tracking
    iteration: int               # current loop number starts at 1
    max_loops: int               # maximum loops allowed
    threshold: int               # pass score
    min_improvement: int         # minimum score gain before stall stop
    scores: list                 # list of int scores per iteration
    previous_score: int          # score from last iteration for stall detection
    best_score: int              # highest score seen across all iterations
    best_draft: str              # draft that achieved best_score

    # Control
    stop_reason: str             # why the loop ended
    should_continue: bool        # True = run another loop iteration

    # Output
    final_output: str            # polished final deliverable

    # Config
    model_main: str
    model_fast: str
    run_dir: str                 # path to run directory for saving files
