"""
tests/test_privacy_guard.py

Phase 7: fail-closed secret scanning and minimal-payload construction.
No test here sends anything anywhere -- these exercise pure functions
against injected fake secret-shaped strings, never a real credential.
"""

import pytest

from orchestrator.privacy_guard import (
    PrivacyGuardError,
    build_minimal_payload,
    guard_payload,
    scan_for_secrets,
)


# ── scan_for_secrets ───────────────────────────────────────────────────────────

def test_scan_for_secrets_catches_anthropic_style_key():
    findings = scan_for_secrets("here is a key: sk-ant-api03-FAKEFAKEFAKEFAKEFAKEFAKE")
    assert findings


def test_scan_for_secrets_catches_openai_style_key():
    findings = scan_for_secrets("OPENAI_API_KEY=sk-FAKEFAKEFAKEFAKEFAKEFAKEFAKE1234")
    assert findings


def test_scan_for_secrets_catches_aws_access_key_id():
    findings = scan_for_secrets("Access key: AKIAFAKEFAKEFAKEFAKE")
    assert findings


def test_scan_for_secrets_catches_env_style_assignment():
    findings = scan_for_secrets("ANTHROPIC_API_KEY=sk-ant-not-a-real-secret-value-123456")
    assert findings


def test_scan_for_secrets_catches_bearer_token():
    findings = scan_for_secrets("Authorization: Bearer abcdef0123456789ABCDEF0123456789")
    assert findings


def test_scan_for_secrets_returns_empty_for_clean_text():
    clean = "This is a perfectly ordinary paragraph about why sleep matters."
    assert scan_for_secrets(clean) == []


# ── build_minimal_payload ──────────────────────────────────────────────────────

def test_build_minimal_payload_for_judge_includes_goal_draft_and_rubric():
    payload = build_minimal_payload(
        "judge", goal="Write a haiku.", draft="An old silent pond...",
        extra={"rubric": "Score for imagery and brevity."},
    )
    assert "Write a haiku." in payload
    assert "An old silent pond..." in payload
    assert "Score for imagery and brevity." in payload


def test_build_minimal_payload_for_judge_excludes_injected_secret_from_other_context():
    """
    Proves the minimal-payload construction actually excludes context it
    wasn't asked to include, rather than merely not mentioning it in the
    function body -- a fake secret placed in an unrelated "extra" key
    (simulating leaked run-context data) must not appear in the judge
    payload, since build_minimal_payload only reads extra["rubric"] for
    that role.
    """
    leaked_secret = "ANTHROPIC_API_KEY=sk-ant-fake-leaked-secret-should-not-appear"
    payload = build_minimal_payload(
        "judge", goal="Write a haiku.", draft="An old silent pond...",
        extra={
            "rubric": "Score for imagery and brevity.",
            "run_dir_contents": leaked_secret,
            "other_agents_output": "unrelated intermediate text",
        },
    )
    assert leaked_secret not in payload
    assert "run_dir_contents" not in payload
    assert "unrelated intermediate text" not in payload


def test_build_minimal_payload_for_synthesizer_includes_only_goal_and_draft():
    payload = build_minimal_payload(
        "synthesizer", goal="Write a haiku.", draft="An old silent pond...",
        extra={"rubric": "This must never appear for synthesizer."},
    )
    assert "Write a haiku." in payload
    assert "An old silent pond..." in payload
    assert "This must never appear for synthesizer." not in payload


def test_build_minimal_payload_for_unknown_role_defaults_to_goal_and_draft_only():
    payload = build_minimal_payload(
        "builder", goal="Write a haiku.", draft="An old silent pond...",
        extra={"rubric": "Should not appear for an unrecognized role."},
    )
    assert "Write a haiku." in payload
    assert "An old silent pond..." in payload
    assert "Should not appear for an unrecognized role." not in payload


# ── guard_payload ──────────────────────────────────────────────────────────────

def test_guard_payload_raises_on_detected_secret():
    tainted = "GOAL:\nWrite something.\n\nDRAFT:\nANTHROPIC_API_KEY=sk-ant-fake123456789"
    with pytest.raises(PrivacyGuardError):
        guard_payload("judge", tainted)


def test_guard_payload_returns_payload_unchanged_when_clean():
    clean = "GOAL:\nWrite a haiku.\n\nDRAFT:\nAn old silent pond..."
    assert guard_payload("judge", clean) == clean
