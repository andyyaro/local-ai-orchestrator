"""
tests/test_model_config.py

Enforces the Phase 6 memory-discipline rule that a 24GB MacBook cannot
keep two 14B-class models resident at once: every profile in
config/models.yaml must reference at most one distinct 14B-class model
name. This is a real enforcement test, not a descriptive one — it fails
the moment a future edit reintroduces a mixed-family profile.
"""

import re
from pathlib import Path

import yaml

from orchestrator.config_loader import VALID_ROLES, get_num_ctx_for_profile

_FOURTEEN_B_PATTERN = re.compile(r"14b|13b", re.IGNORECASE)


def _load_profiles() -> dict:
    path = Path("config/models.yaml")
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg["profiles"]


def _fourteen_b_models(role_models: dict) -> set:
    return {model for model in role_models.values() if _FOURTEEN_B_PATTERN.search(model)}


def test_every_profile_defines_all_valid_roles():
    profiles = _load_profiles()
    for name, roles in profiles.items():
        assert set(roles.keys()) == VALID_ROLES, (
            f"profile '{name}' does not define exactly VALID_ROLES: "
            f"missing {VALID_ROLES - set(roles.keys())}, "
            f"extra {set(roles.keys()) - VALID_ROLES}"
        )


def test_every_profile_has_at_most_one_distinct_14b_class_model():
    profiles = _load_profiles()
    for name, roles in profiles.items():
        fourteen_b = _fourteen_b_models(roles)
        assert len(fourteen_b) <= 1, (
            f"profile '{name}' references multiple distinct 14B-class "
            f"models, which cannot co-reside on a 24GB Mac: {fourteen_b}"
        )


def test_low_memory_profile_has_zero_14b_class_models():
    profiles = _load_profiles()
    assert _fourteen_b_models(profiles["low_memory"]) == set()


def test_serious_and_coding_profiles_each_use_exactly_one_14b_class_model():
    profiles = _load_profiles()
    assert len(_fourteen_b_models(profiles["serious"])) == 1
    assert len(_fourteen_b_models(profiles["coding"])) == 1


def test_get_num_ctx_for_profile_is_smaller_for_low_memory_than_serious():
    assert get_num_ctx_for_profile("low_memory") < get_num_ctx_for_profile("serious")


def test_get_num_ctx_for_profile_falls_back_to_default_for_unlisted_profile():
    from orchestrator.config_loader import get_inference_defaults

    assert get_num_ctx_for_profile("nonexistent_profile") == int(
        get_inference_defaults().get("num_ctx", 4096)
    )
