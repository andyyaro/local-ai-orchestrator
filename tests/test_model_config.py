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

from orchestrator.config_loader import (
    VALID_ROLES,
    get_effective_role_models,
    get_num_ctx_for_profile,
)

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


# ── get_effective_role_models: mode_overrides can't reintroduce mixed 14B families ──
#
# Regression coverage for the Phase 6b memory-discipline gap: mode_overrides
# apply regardless of active_profile, so active_profile=serious + a goal
# classified mode="coding" used to switch builder/fixer to
# qwen2.5-coder:14b while judge/synthesizer stayed on serious's
# qwen2.5:14b -- two resident 14B-class families in one run, even though
# each of "serious" and the "coding" mode_overrides look fine viewed in
# isolation (which is exactly why tests/test_model_config.py's per-profile
# checks above couldn't catch it).

def test_effective_role_models_for_serious_profile_with_coding_mode_uses_one_14b_family():
    effective = get_effective_role_models(mode="coding", profile_name="serious")

    fourteen_b_models = {
        model for model in effective.values() if _FOURTEEN_B_PATTERN.search(model)
    }
    assert len(fourteen_b_models) == 1


def test_effective_role_models_for_serious_profile_with_coding_mode_uses_the_override_model():
    effective = get_effective_role_models(mode="coding", profile_name="serious")

    # builder/fixer are explicitly overridden for mode="coding"; judge and
    # synthesizer are not listed in mode_overrides but must be brought in
    # line with the override's model rather than left on serious's own
    # qwen2.5:14b, since that would still leave two resident 14B families.
    assert effective["builder"] == "qwen2.5-coder:14b"
    assert effective["fixer"] == "qwen2.5-coder:14b"
    assert effective["judge"] == "qwen2.5-coder:14b"
    assert effective["synthesizer"] == "qwen2.5-coder:14b"


def test_effective_role_models_for_serious_profile_with_debugging_mode_uses_one_14b_family():
    effective = get_effective_role_models(mode="debugging", profile_name="serious")

    fourteen_b_models = {
        model for model in effective.values() if _FOURTEEN_B_PATTERN.search(model)
    }
    assert len(fourteen_b_models) == 1


def test_effective_role_models_for_general_mode_is_unchanged_from_profile():
    from orchestrator.config_loader import get_profile_models

    effective = get_effective_role_models(mode="general", profile_name="serious")
    assert effective == get_profile_models("serious")


def test_effective_role_models_for_low_memory_profile_with_coding_mode_stays_single_14b():
    # low_memory has zero 14B models before the override; the coding
    # override introduces exactly one (builder/fixer), which is already
    # within the "at most one" rule and should not be expanded further.
    effective = get_effective_role_models(mode="coding", profile_name="low_memory")

    fourteen_b_models = {
        model for model in effective.values() if _FOURTEEN_B_PATTERN.search(model)
    }
    assert fourteen_b_models == {"qwen2.5-coder:14b"}
    assert effective["judge"] == "llama3.2:3b"
    assert effective["synthesizer"] == "llama3.1:8b"


def test_get_model_for_role_reflects_effective_role_models(monkeypatch):
    from orchestrator import config_loader

    monkeypatch.setattr(config_loader, "get_active_profile", lambda: "serious")
    # get_model_for_role("judge", mode="coding") must resolve through the
    # same mode_overrides + profile mixing-prevention as
    # get_effective_role_models(), not the raw mode_overrides lookup that
    # existed before this phase (which would have returned "serious"'s own
    # qwen2.5:14b for judge, since judge isn't listed in mode_overrides).
    assert config_loader.get_model_for_role("judge", mode="coding") == "qwen2.5-coder:14b"
