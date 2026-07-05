"""
tests/test_mode_classifier.py

Phase 12b: deterministic coding-signal detection, the backstop for the
Supervisor's own LLM-based mode classification. Pure string matching --
no model call involved.
"""

import pytest

from orchestrator.mode_classifier import has_obvious_coding_signal


@pytest.mark.parametrize("goal", [
    "Write a Python function called double(n) that returns n * 2.",
    "Fix this bug in my script.",
    "There's a traceback I don't understand, can you help debug it?",
    "Write unit tests for this class using pytest.",
    "Refactor this function to be more readable.",
    "Implement a CLI tool that reads a CSV file.",
    "Write a JavaScript function to validate an email address.",
    "Design a SQL query to join these two tables.",
    "Build a REST API endpoint in TypeScript.",
    "Add a new HTML page with some CSS styling.",
    "Clone this repository and make some file edits.",
    "Write a program that sorts a list of numbers.",
])
def test_has_obvious_coding_signal_true_for_coding_goals(goal):
    assert has_obvious_coding_signal(goal) is True


@pytest.mark.parametrize("goal", [
    "Write a 300-word essay about the history of sleep research.",
    "Create a project plan for launching a new product.",
    "Explain how photosynthesis works to a beginner.",
    "Summarize the water cycle in exactly 120 words.",
    "Write a short story about a lighthouse keeper.",
])
def test_has_obvious_coding_signal_false_for_non_coding_goals(goal):
    assert has_obvious_coding_signal(goal) is False


def test_has_obvious_coding_signal_does_not_false_positive_on_substring():
    """Word-boundary matching must not trigger on "class" inside
    "classic" or "code" inside "codependent"."""
    assert has_obvious_coding_signal("Write an essay about classic literature.") is False
    assert has_obvious_coding_signal("Explain codependent relationships in psychology.") is False
