"""
tests/test_cloud_policy.py

Phase 7: off-by-default policy gates. All checks here exercise the real
config-driven logic in orchestrator/cloud_policy.py; none of them call
request_human_approval() for real (it blocks on terminal input() and must
never run in a test process -- see that function's docstring).
"""

from orchestrator import cloud_policy


def test_is_cloud_enabled_is_false_by_default_against_shipped_config():
    """The shipped config/models.yaml has cloud.enabled: false and
    provider: ollama -- both must independently agree for this to be
    True, so against the real, unmodified config it must be False."""
    assert cloud_policy.is_cloud_enabled() is False


def test_is_cloud_enabled_true_requires_both_flags(monkeypatch):
    monkeypatch.setattr(cloud_policy, "get_provider", lambda: "anthropic")
    monkeypatch.setattr(cloud_policy, "get_cloud_config", lambda: {"enabled": True})
    assert cloud_policy.is_cloud_enabled() is True


def test_is_cloud_enabled_false_if_provider_still_ollama_even_when_cloud_enabled_true(monkeypatch):
    """Defense in depth: cloud.enabled: true alone can never flip this on
    if the top-level provider is still "ollama"."""
    monkeypatch.setattr(cloud_policy, "get_provider", lambda: "ollama")
    monkeypatch.setattr(cloud_policy, "get_cloud_config", lambda: {"enabled": True})
    assert cloud_policy.is_cloud_enabled() is False


def test_is_cloud_enabled_false_if_cloud_config_enabled_false_even_when_provider_anthropic(monkeypatch):
    monkeypatch.setattr(cloud_policy, "get_provider", lambda: "anthropic")
    monkeypatch.setattr(cloud_policy, "get_cloud_config", lambda: {"enabled": False})
    assert cloud_policy.is_cloud_enabled() is False


def test_is_role_allowed_true_for_judge_and_synthesizer_by_default():
    assert cloud_policy.is_role_allowed("judge") is True
    assert cloud_policy.is_role_allowed("synthesizer") is True


def test_is_role_allowed_false_for_other_roles_by_default():
    for role in ("supervisor", "planner", "builder", "critic", "fixer"):
        assert cloud_policy.is_role_allowed(role) is False


def test_is_role_allowed_respects_explicit_config_list(monkeypatch):
    monkeypatch.setattr(cloud_policy, "get_cloud_config", lambda: {"allowed_roles": ["builder"]})
    assert cloud_policy.is_role_allowed("builder") is True
    assert cloud_policy.is_role_allowed("judge") is False


def test_should_attempt_cloud_requires_both_enabled_and_role_allowed(monkeypatch):
    monkeypatch.setattr(cloud_policy, "is_cloud_enabled", lambda: True)
    monkeypatch.setattr(cloud_policy, "is_role_allowed", lambda role: role == "judge")
    assert cloud_policy.should_attempt_cloud("judge") is True
    assert cloud_policy.should_attempt_cloud("builder") is False


def test_should_attempt_cloud_false_when_cloud_disabled_even_if_role_allowed(monkeypatch):
    monkeypatch.setattr(cloud_policy, "is_cloud_enabled", lambda: False)
    monkeypatch.setattr(cloud_policy, "is_role_allowed", lambda role: True)
    assert cloud_policy.should_attempt_cloud("judge") is False


def test_should_attempt_cloud_false_against_real_shipped_config_for_every_role():
    """End-to-end confirmation against the real config: with cloud.enabled
    false shipped by default, no role should ever be attempted."""
    for role in ("judge", "synthesizer", "builder", "supervisor"):
        assert cloud_policy.should_attempt_cloud(role) is False


def test_request_human_approval_returns_true_only_for_literal_y(monkeypatch):
    """Confirms the approval gate's string-matching logic without ever
    calling the real input()-based function -- monkeypatch builtins.input
    so this stays a fast, deterministic unit test."""
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    assert cloud_policy.request_human_approval("judge", "preview text", 0.01) is True


def test_request_human_approval_returns_false_for_anything_else(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt="": "yes")
    assert cloud_policy.request_human_approval("judge", "preview text", 0.01) is False

    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    assert cloud_policy.request_human_approval("judge", "preview text", 0.01) is False

    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    assert cloud_policy.request_human_approval("judge", "preview text", 0.01) is False
