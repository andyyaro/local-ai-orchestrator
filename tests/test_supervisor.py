"""
tests/test_supervisor.py

Phase 12b: exercises the real SupervisorAgent.run() parsing and
deterministic coding-mode override logic, with call_model mocked so no
real model call happens. This is the regression coverage for the
verified bug: a real run classified an unambiguous coding goal as
mode="general".
"""

from agents.supervisor import SupervisorAgent


def _agent_with_canned_response(monkeypatch, raw_response: str) -> SupervisorAgent:
    monkeypatch.setattr(SupervisorAgent, "call_model", lambda self, prompt: raw_response)
    return SupervisorAgent(model="test-model")


def test_supervisor_overrides_general_to_coding_for_obvious_coding_goal(monkeypatch):
    """The exact regression this phase fixes: the model itself picked
    "general" for an unambiguous coding goal."""
    agent = _agent_with_canned_response(
        monkeypatch,
        "REFINED GOAL: Write a Python function called double(n) that returns n * 2.\n"
        "MODE: general",
    )
    result = agent.run(
        goal=(
            "Write a Python function called double(n) that returns n "
            "multiplied by 2. Include a pytest test asserting double(5) == 10."
        )
    )
    assert result["mode"] == "coding"


def test_supervisor_does_not_override_when_model_already_says_coding(monkeypatch):
    agent = _agent_with_canned_response(
        monkeypatch, "REFINED GOAL: Write a function.\nMODE: coding",
    )
    result = agent.run(goal="Write a function that adds two numbers.")
    assert result["mode"] == "coding"


def test_supervisor_does_not_override_when_model_says_debugging(monkeypatch):
    agent = _agent_with_canned_response(
        monkeypatch, "REFINED GOAL: Fix this traceback.\nMODE: debugging",
    )
    result = agent.run(goal="Fix this bug: TypeError in my script.")
    assert result["mode"] == "debugging"


def test_supervisor_leaves_non_coding_goal_alone(monkeypatch):
    agent = _agent_with_canned_response(
        monkeypatch,
        "REFINED GOAL: Write a 300-word essay about the history of sleep research.\n"
        "MODE: writing",
    )
    result = agent.run(goal="Write a 300-word essay about the history of sleep research.")
    assert result["mode"] == "writing"


def test_supervisor_overrides_even_when_model_picks_writing_for_coding_goal(monkeypatch):
    agent = _agent_with_canned_response(
        monkeypatch, "REFINED GOAL: Document how the API works.\nMODE: writing",
    )
    result = agent.run(
        goal="Write a Python script implementing a REST API client with unit tests."
    )
    assert result["mode"] == "coding"


def test_supervisor_parses_refined_goal_and_mode_normally_when_no_override_needed(monkeypatch):
    """Confirms the override doesn't interfere with ordinary parsing."""
    agent = _agent_with_canned_response(
        monkeypatch,
        "REFINED GOAL: Explain how photosynthesis works to a beginner.\nMODE: study",
    )
    result = agent.run(goal="Explain photosynthesis simply.")
    assert result["mode"] == "study"
    assert result["refined_goal"] == "Explain how photosynthesis works to a beginner."
