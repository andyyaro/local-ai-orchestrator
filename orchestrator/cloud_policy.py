"""
orchestrator/cloud_policy.py

Off-by-default policy gates for the optional cloud fallback (Phase 7).
should_attempt_cloud() is the single function every call site must check
before doing anything cloud-related -- it combines the config toggle with
a second, independent provider check, so two separate config values both
have to agree before any cloud path is even considered.

This module never makes a network call. It only decides whether a call
would be allowed, and (via request_human_approval) asks a human before one
ever happens.
"""

from orchestrator.config_loader import get_cloud_config, get_provider

_DEFAULT_ALLOWED_ROLES = ("judge", "synthesizer")


def is_cloud_enabled() -> bool:
    """
    Return True only if cloud.enabled is true in config/models.yaml AND
    the top-level provider is not "ollama". These are two independent
    checks that both must agree -- defense in depth, so a single flipped
    config flag can never enable a real cloud call on its own.
    """
    if get_provider() == "ollama":
        return False
    return bool(get_cloud_config().get("enabled", False))


def is_role_allowed(role: str) -> bool:
    """
    Return True only if `role` is in cloud.allowed_roles. Only "judge" and
    "synthesizer" are allowed by default -- expanding this list requires an
    explicit edit to config/models.yaml, never a silent code change.
    """
    allowed = get_cloud_config().get("allowed_roles", list(_DEFAULT_ALLOWED_ROLES))
    return role in allowed


def should_attempt_cloud(role: str) -> bool:
    """
    The single check every cloud call site must pass before doing
    anything cloud-related. Combines is_cloud_enabled() and
    is_role_allowed(role) -- both must be true.
    """
    return is_cloud_enabled() and is_role_allowed(role)


def request_human_approval(role: str, payload_preview: str, estimated_cost_usd: float) -> bool:
    """
    Print the exact payload that would be sent (in full -- never truncated
    in a way that could hide something) and the estimated cost, then read
    a y/n confirmation from the terminal. Returns False for anything other
    than an explicit "y".

    IMPORTANT: this function blocks on real terminal input() and must
    NEVER be called from a non-interactive context (CI, an automated
    script, a test). Tests must monkeypatch or stub this function out
    rather than invoke it for real -- calling it in a non-interactive
    process will hang or raise on EOF.
    """
    print("=" * 70)
    print(f"CLOUD ESCALATION REQUEST -- role: {role}")
    print("=" * 70)
    print(payload_preview)
    print("-" * 70)
    print(f"Estimated cost: ${estimated_cost_usd:.4f} USD")
    print("=" * 70)
    response = input("Send this payload to the cloud provider? [y/N]: ")
    return response.strip().lower() == "y"
