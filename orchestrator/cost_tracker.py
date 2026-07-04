"""
orchestrator/cost_tracker.py

Token-based cost estimation and budget enforcement for the optional cloud
fallback (Phase 7). Every real dollar figure here comes from
config/models.yaml's cloud.pricing and cloud.budget blocks -- nothing in
this module makes a network call; it only estimates, checks, and records.
"""

from orchestrator.config_loader import get_cloud_config
from orchestrator.database import get_cloud_spend, save_cloud_call


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    """
    Estimate the USD cost of a cloud call from token counts and
    config/models.yaml's cloud.pricing block.

    This is an estimate, not an exact figure: real provider tokenization
    differs slightly from whatever local approximation a caller used to
    count tokens (e.g. len(text) // 4), so treat this as a budget-safety
    upper bound to check against, not an exact invoice prediction.
    """
    pricing = get_cloud_config().get("pricing", {})
    input_rate = float(pricing.get("input_per_million_usd", 0))
    output_rate = float(pricing.get("output_per_million_usd", 0))
    return (input_tokens / 1_000_000) * input_rate + (output_tokens / 1_000_000) * output_rate


def get_spend(period: str) -> float:
    """Return total recorded cloud_calls spend for the "daily" or
    "monthly" window (see orchestrator.database.get_cloud_spend)."""
    return get_cloud_spend(period)


def check_budget(estimated_cost_usd: float) -> bool:
    """
    Return False if adding a call costing `estimated_cost_usd` would
    exceed cloud.budget's per_run_usd, daily_usd, or monthly_usd, and
    cloud.budget.block_over_budget is true (the default). Must be checked
    *before* requesting human approval, so a user is never asked to
    approve a call that's already over budget.
    """
    budget = get_cloud_config().get("budget", {})
    if not budget.get("block_over_budget", True):
        return True

    per_run_limit = budget.get("per_run_usd")
    if per_run_limit is not None and estimated_cost_usd > float(per_run_limit):
        return False

    daily_limit = budget.get("daily_usd")
    if daily_limit is not None and get_spend("daily") + estimated_cost_usd > float(daily_limit):
        return False

    monthly_limit = budget.get("monthly_usd")
    if monthly_limit is not None and get_spend("monthly") + estimated_cost_usd > float(monthly_limit):
        return False

    return True


def record_call(
    run_id: int | None,
    role: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    approved: bool,
) -> int:
    """Persist one cloud escalation attempt to the cloud_calls table."""
    provider = get_cloud_config().get("provider", "unknown")
    return save_cloud_call(
        run_id=run_id,
        role=role,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        approved_by_user=approved,
    )
