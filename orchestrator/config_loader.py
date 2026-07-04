"""
orchestrator/config_loader.py

Loads and caches configuration from config/models.yaml and config/modes.yaml.
All pipeline code should use these helpers instead of reading YAML directly.
"""

import re
from pathlib import Path
import yaml

_CONFIG_DIR = Path("config")
_models_cache = None
_modes_cache = None

VALID_ROLES = {
    "supervisor",
    "planner",
    "builder",
    "critic",
    "fixer",
    "judge",
    "synthesizer",
}

# Same heuristic tests/test_model_config.py uses to enforce "at most one
# distinct 14B-class model per profile" -- reused here so mode_overrides
# can't silently reintroduce a second resident 14B-class family alongside
# the active profile's own (see get_effective_role_models()).
_FOURTEEN_B_PATTERN = re.compile(r"14b|13b", re.IGNORECASE)


def load_models_config() -> dict:
    """Load config/models.yaml once and return the cached dict."""
    global _models_cache
    if _models_cache is None:
        path = _CONFIG_DIR / "models.yaml"
        with open(path, encoding="utf-8") as f:
            _models_cache = yaml.safe_load(f) or {}
    return _models_cache


def load_modes_config() -> dict:
    """Load config/modes.yaml once and return the cached dict."""
    global _modes_cache
    if _modes_cache is None:
        path = _CONFIG_DIR / "modes.yaml"
        with open(path, encoding="utf-8") as f:
            _modes_cache = yaml.safe_load(f) or {}
    return _modes_cache


def get_provider() -> str:
    """Return the active provider name, such as 'ollama'."""
    return load_models_config().get("provider", "ollama")


def get_active_profile() -> str:
    """Return the active model profile name."""
    return load_models_config().get("active_profile", "bootstrap")


def get_profile_models(profile_name: str | None = None) -> dict:
    """Return role-to-model mapping for the selected profile."""
    cfg = load_models_config()
    profile = profile_name or get_active_profile()
    profiles = cfg.get("profiles", {})
    if profile not in profiles:
        raise ValueError(
            f"Unknown active_profile '{profile}' in config/models.yaml. "
            f"Valid options: {', '.join(profiles.keys())}"
        )
    return profiles[profile]


def get_effective_role_models(mode: str = "general", profile_name: str | None = None) -> dict:
    """
    Return the full role->model mapping for `profile_name` (default: the
    active profile) with `mode`'s mode_overrides applied, corrected so at
    most one distinct 14B-class model family is used across all seven
    roles for this profile+mode combination.

    mode_overrides alone can otherwise reintroduce the multi-14B-model
    swap problem Phase 6 fixed at the profile level: e.g.
    active_profile=serious + mode=coding would, without this correction,
    switch builder/fixer to qwen2.5-coder:14b via the override while
    judge/synthesizer stayed on serious's qwen2.5:14b -- two resident
    14B-class families for that one run, even though each of "serious"
    and the override individually look fine in isolation.

    When an override introduces a second 14B-class family, every other
    role currently on a (different) 14B-class model is brought in line
    with the override's model, since the override is the more
    task-relevant choice (e.g. a coder-specific model for a
    coding-classified goal).
    """
    cfg = load_models_config()
    effective = dict(get_profile_models(profile_name))
    overrides = cfg.get("mode_overrides", {}).get(mode, {})
    effective.update(overrides)

    fourteen_b_models = {
        model for model in effective.values() if _FOURTEEN_B_PATTERN.search(model)
    }
    if len(fourteen_b_models) > 1:
        override_14b = {
            model for model in overrides.values() if _FOURTEEN_B_PATTERN.search(model)
        }
        target = next(iter(override_14b)) if override_14b else next(iter(fourteen_b_models))
        for role, model in effective.items():
            if _FOURTEEN_B_PATTERN.search(model) and model != target:
                effective[role] = target

    return effective


def get_model_for_role(role: str, mode: str = "general") -> str:
    """
    Return the model name for a given agent role and optional workflow mode.
    Checks mode_overrides first, then falls back to the active profile, with
    get_effective_role_models() ensuring the two never combine into more
    than one resident 14B-class model family.
    """
    if role not in VALID_ROLES:
        raise ValueError(f"Unknown model role '{role}'. Valid roles: {sorted(VALID_ROLES)}")

    return get_effective_role_models(mode).get(role, "llama3.2:3b")


def get_ollama_base_url() -> str:
    cfg = load_models_config()
    return cfg.get("ollama", {}).get("base_url", "http://localhost:11434")


def get_ollama_timeout() -> int:
    """Return Ollama HTTP timeout in seconds."""
    cfg = load_models_config()
    return int(cfg.get("ollama", {}).get("request_timeout", 600))


def get_inference_defaults() -> dict:
    cfg = load_models_config()
    return cfg.get("defaults", {"temperature": 0.7, "num_ctx": 4096})


def get_num_ctx_for_profile(profile_name: str | None = None) -> int:
    """Return the context window size for a profile from
    config/models.yaml's context_sizes block, falling back to
    defaults.num_ctx if the profile has no explicit entry."""
    cfg = load_models_config()
    profile = profile_name or get_active_profile()
    context_sizes = cfg.get("context_sizes", {})
    if profile in context_sizes:
        return int(context_sizes[profile])
    return int(get_inference_defaults().get("num_ctx", 4096))


def get_keep_alive() -> str:
    cfg = load_models_config()
    memory_keep_alive = cfg.get("memory", {}).get("keep_alive")
    ollama_keep_alive = cfg.get("ollama", {}).get("keep_alive")
    return memory_keep_alive or ollama_keep_alive or "5m"


def get_path_settings(path_name: str) -> dict:
    """Return the routing settings (skip_planner, skip_critic_fixer_loop,
    max_loops, threshold) for a given path name (fast | normal | deep)."""
    cfg = load_models_config()
    paths = cfg.get("paths", {})
    if path_name not in paths:
        raise ValueError(
            f"Unknown path '{path_name}' in config/models.yaml. "
            f"Valid options: {', '.join(paths.keys())}"
        )
    return paths[path_name]


def get_resilience_config() -> dict:
    """Return the resilience section (timeouts, fallback_model,
    max_local_retries, cloud_backoff) from config/models.yaml."""
    cfg = load_models_config()
    return cfg.get("resilience", {})


def get_cloud_config() -> dict:
    """Return the Phase 7 cloud section (enabled, provider, model,
    allowed_roles, budget, pricing) from config/models.yaml. Returns an
    empty dict (all downstream checks treat this as "disabled") if the
    section is absent entirely."""
    cfg = load_models_config()
    return cfg.get("cloud", {})


def reload_config():
    """Force reload of cached configs after editing YAML files."""
    global _models_cache, _modes_cache
    _models_cache = None
    _modes_cache = None
