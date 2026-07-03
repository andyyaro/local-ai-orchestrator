"""
orchestrator/modes.py

Loads workflow mode configuration from config/modes.yaml.
Provides helpers to get the prompt suffix, scoring weights, judge note,
and expected output format for a given mode.
"""

from pathlib import Path
import yaml


_MODES_PATH = Path("config") / "modes.yaml"
_modes_cache = None


def _load_modes() -> dict:
    global _modes_cache
    if _modes_cache is None:
        with open(_MODES_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        _modes_cache = data.get("modes", {})
    return _modes_cache


def get_mode_config(mode: str) -> dict:
    """Return full config for a mode, falling back to general."""
    modes = _load_modes()
    return modes.get(mode, modes.get("general", {}))


def get_prompt_suffix(mode: str) -> str:
    """Return the prompt suffix string for a given mode."""
    return get_mode_config(mode).get("prompt_suffix", "").strip()


def get_scoring_weights(mode: str) -> dict:
    """Return scoring weights for a given mode."""
    return get_mode_config(mode).get("scoring_weights", {
        "completeness": 25,
        "accuracy": 25,
        "clarity": 25,
        "usefulness": 25,
    })


def get_judge_note(mode: str) -> str:
    """Return the extra judge instruction for a given mode."""
    return get_mode_config(mode).get("judge_note", "").strip()


def get_output_format(mode: str) -> str:
    """Return the expected output format description for a given mode."""
    return get_mode_config(mode).get("output_format", "").strip()


def list_modes() -> list[str]:
    """Return all available mode names."""
    return list(_load_modes().keys())
