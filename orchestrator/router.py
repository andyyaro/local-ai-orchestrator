"""
orchestrator/router.py

Deterministic (no model call) routing of a goal to a fast/normal/deep
pipeline path, based on goal length, complexity keywords, and mode.
"""

from orchestrator.config_loader import get_path_settings

# A goal at or under this many words, with no complexity signal, is
# considered simple enough for the fast path.
FAST_PATH_WORD_THRESHOLD = 25

# Modes that always imply the deep path, since coding/debugging tasks
# tend to need the full critique/fix/judge loop to catch real errors.
DEEP_PATH_MODES = {"coding", "debugging"}

# Presence of any of these phrases in the goal implies the task wants
# more thoroughness than the fast/normal path provides.
DEEP_PATH_KEYWORDS = [
    "comprehensive",
    "thorough",
    "in-depth",
    "in depth",
    "step by step",
    "step-by-step",
    "with tests",
    "handle edge cases",
    "edge cases",
]

VALID_PATHS = {"fast", "normal", "deep"}


def classify_path(goal: str, mode: str, override: str | None = None) -> str:
    """Return "fast", "normal", or "deep" for the given goal and mode.

    If `override` is given, it is returned directly with no heuristic
    evaluation at all.
    """
    if override:
        return override

    goal_lower = goal.lower()

    if mode in DEEP_PATH_MODES:
        return "deep"
    if any(keyword in goal_lower for keyword in DEEP_PATH_KEYWORDS):
        return "deep"

    word_count = len(goal.split())
    if word_count <= FAST_PATH_WORD_THRESHOLD:
        return "fast"

    return "normal"


def get_path_config(path: str) -> dict:
    """Thin wrapper around config_loader.get_path_settings(path)."""
    return get_path_settings(path)
