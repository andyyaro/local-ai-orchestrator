"""Judge agent.

Scores the revised output against a mode-specific rubric.
"""

from __future__ import annotations


def run_judge(goal: str, revised_output: str) -> dict[str, object]:
    """Placeholder implementation for the Judge role."""
    return {
        "score": 0,
        "pass": False,
        "rationale": "Judge implementation pending.",
        "goal": goal,
        "output_preview": revised_output[:200],
    }
