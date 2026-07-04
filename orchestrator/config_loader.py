"""
orchestrator/config_loader.py

Loads and caches configuration from config/models.yaml and config/modes.yaml.
All pipeline code should use these helpers instead of reading YAML directly.
"""

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


def get_model_for_role(role: str, mode: str = "general") -> str:
    """
    Return the model name for a given agent role and optional workflow mode.
    Checks mode_overrides first, then falls back to the active profile.
    """
    if role not in VALID_ROLES:
        raise ValueError(f"Unknown model role '{role}'. Valid roles: {sorted(VALID_ROLES)}")

    cfg = load_models_config()
    mode_overrides = cfg.get("mode_overrides", {}).get(mode, {})
    if role in mode_overrides:
        return mode_overrides[role]

    models = get_profile_models()
    return models.get(role, "llama3.2:3b")


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


def reload_config():
    """Force reload of cached configs after editing YAML files."""
    global _models_cache, _modes_cache
    _models_cache = None
    _modes_cache = None
