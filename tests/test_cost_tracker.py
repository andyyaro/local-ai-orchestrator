"""
tests/test_cost_tracker.py

Phase 7: cost estimation and budget enforcement. Every test here uses a
temp SQLite database (never runs/history.db) and monkeypatches
cloud_config so pricing/budget numbers are deterministic and independent
of config/models.yaml's real (unverified, placeholder) values.
"""

import pytest

from orchestrator import cost_tracker, database


def _patch_cloud_config(monkeypatch, **overrides):
    config = {
        "provider": "anthropic",
        "pricing": {"input_per_million_usd": 2.00, "output_per_million_usd": 10.00},
        "budget": {
            "per_run_usd": 0.25,
            "daily_usd": 2.00,
            "monthly_usd": 20.00,
            "block_over_budget": True,
        },
    }
    config.update(overrides)
    monkeypatch.setattr(cost_tracker, "get_cloud_config", lambda: config)
    return config


# ── estimate_cost ──────────────────────────────────────────────────────────────

def test_estimate_cost_matches_hand_computed_value_for_one_million_tokens_each(monkeypatch):
    _patch_cloud_config(monkeypatch)
    # 1,000,000 input tokens @ $2.00/M + 1,000,000 output tokens @ $10.00/M
    assert cost_tracker.estimate_cost(1_000_000, 1_000_000) == 12.00


def test_estimate_cost_matches_hand_computed_value_for_partial_million(monkeypatch):
    _patch_cloud_config(monkeypatch)
    # 500,000 input tokens @ $2.00/M = $1.00; 100,000 output @ $10.00/M = $1.00
    assert cost_tracker.estimate_cost(500_000, 100_000) == 2.00


def test_estimate_cost_zero_tokens_is_zero_cost(monkeypatch):
    _patch_cloud_config(monkeypatch)
    assert cost_tracker.estimate_cost(0, 0) == 0.00


# ── check_budget ─────────────────────────────────────────────────────────────

def test_check_budget_blocks_call_exceeding_per_run_usd(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "history.db")
    _patch_cloud_config(monkeypatch)
    assert cost_tracker.check_budget(0.50) is False
    assert cost_tracker.check_budget(0.10) is True


def test_check_budget_blocks_call_exceeding_daily_usd_with_seeded_prior_calls(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "history.db")
    _patch_cloud_config(monkeypatch, budget={
        "per_run_usd": 5.00, "daily_usd": 2.00, "monthly_usd": 20.00,
        "block_over_budget": True,
    })

    # Seed $1.80 of prior spend today -- a further $0.30 call would push
    # the daily total to $2.10, over the $2.00 daily_usd limit.
    database.save_cloud_call(
        run_id=None, role="judge", provider="anthropic", model="claude-sonnet-5",
        input_tokens=100, output_tokens=100, cost_usd=1.80, approved_by_user=True,
    )

    assert cost_tracker.check_budget(0.30) is False
    assert cost_tracker.check_budget(0.10) is True


def test_check_budget_blocks_call_exceeding_monthly_usd_with_seeded_prior_calls(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "history.db")
    _patch_cloud_config(monkeypatch, budget={
        "per_run_usd": 5.00, "daily_usd": 50.00, "monthly_usd": 20.00,
        "block_over_budget": True,
    })

    database.save_cloud_call(
        run_id=None, role="judge", provider="anthropic", model="claude-sonnet-5",
        input_tokens=100, output_tokens=100, cost_usd=19.90, approved_by_user=True,
    )

    assert cost_tracker.check_budget(0.20) is False
    assert cost_tracker.check_budget(0.05) is True


def test_check_budget_allows_over_budget_call_when_block_over_budget_false(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "history.db")
    _patch_cloud_config(monkeypatch, budget={
        "per_run_usd": 0.01, "daily_usd": 0.01, "monthly_usd": 0.01,
        "block_over_budget": False,
    })
    assert cost_tracker.check_budget(1000.00) is True


# ── record_call / get_spend ──────────────────────────────────────────────────

def test_record_call_writes_row_and_get_spend_reflects_it(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "history.db")
    _patch_cloud_config(monkeypatch)

    assert cost_tracker.get_spend("daily") == 0.0

    cost_tracker.record_call(
        run_id=None, role="synthesizer", model="claude-sonnet-5",
        input_tokens=1000, output_tokens=500, cost_usd=0.15, approved=True,
    )

    assert cost_tracker.get_spend("daily") == 0.15
    assert cost_tracker.get_spend("monthly") == 0.15


def test_get_spend_sums_multiple_recorded_calls(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "history.db")
    _patch_cloud_config(monkeypatch)

    cost_tracker.record_call(None, "judge", "claude-sonnet-5", 100, 100, 0.05, True)
    cost_tracker.record_call(None, "synthesizer", "claude-sonnet-5", 200, 200, 0.10, True)

    assert cost_tracker.get_spend("daily") == pytest.approx(0.15)
