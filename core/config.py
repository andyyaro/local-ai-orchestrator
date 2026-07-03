"""Configuration helpers for the Local AI Orchestrator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"


class ConfigError(RuntimeError):
    """Raised when a configuration file is missing or invalid."""


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file and return a dictionary."""
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    if not isinstance(data, dict):
        raise ConfigError(f"Config file must contain a YAML mapping: {path}")

    return data


def load_model_config() -> dict[str, Any]:
    """Load config/models.yaml."""
    return load_yaml(CONFIG_DIR / "models.yaml")


def get_active_profile(config: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
    """Return the active model profile name and profile settings."""
    model_config = config or load_model_config()
    active_profile = model_config.get("active_profile")
    profiles = model_config.get("profiles", {})

    if not isinstance(active_profile, str):
        raise ConfigError("models.yaml must define active_profile as a string.")

    if not isinstance(profiles, dict) or active_profile not in profiles:
        raise ConfigError(f"Active profile '{active_profile}' is not defined in models.yaml.")

    profile = profiles[active_profile]
    if not isinstance(profile, dict):
        raise ConfigError(f"Profile '{active_profile}' must be a YAML mapping.")

    return active_profile, profile


def get_model_for_role(role: str, profile: dict[str, Any]) -> str:
    """Return the configured model name for an agent role."""
    model = profile.get(role)
    if not isinstance(model, str) or not model:
        raise ConfigError(f"Model role '{role}' is missing from the active profile.")
    return model
