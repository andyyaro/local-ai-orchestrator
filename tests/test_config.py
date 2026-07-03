"""Tests for configuration helpers."""

from __future__ import annotations

from core.config import get_active_profile, get_model_for_role


def test_get_active_profile_reads_bootstrap_profile() -> None:
    config = {
        "active_profile": "bootstrap",
        "profiles": {
            "bootstrap": {
                "supervisor": "llama3.2:3b",
                "keep_alive": "5m",
            }
        },
    }

    name, profile = get_active_profile(config)

    assert name == "bootstrap"
    assert profile["supervisor"] == "llama3.2:3b"


def test_get_model_for_role_returns_configured_model() -> None:
    profile = {"supervisor": "llama3.2:3b"}

    assert get_model_for_role("supervisor", profile) == "llama3.2:3b"
