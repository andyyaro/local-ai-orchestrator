"""
orchestrator/mode_classifier.py

Deterministic (no model call) detection of obvious coding-task signals in
a user's raw goal text -- the backstop for Phase 12b's finding that the
Supervisor's own LLM-based mode classification can misclassify an
unambiguous coding goal as mode="general" (verified: a real run
classified "Write a Python function called double(n) that returns n
multiplied by 2. Include a pytest test..." as mode="general" using the
serious profile's default supervisor model). Mirrors
orchestrator/router.py's existing deterministic-keyword-based design,
which does the same thing for fast/normal/deep path classification.

Precision/recall tradeoff, stated plainly: several of these signal words
("error", "bug", "class", "script", "api") can appear in genuinely
non-coding prose (e.g. "human error", "a bug in the plan"). This module
deliberately favors recall -- catching the reported misclassification
bug -- per this phase's explicit signal list, over avoiding every
possible false positive. Word-boundary matching (\\b) at least prevents
substring false positives like "class" inside "classic".
"""

import re

_CODING_SIGNAL_PATTERNS = [
    re.compile(r"\bcode\b", re.IGNORECASE),
    re.compile(r"\bfunction\b", re.IGNORECASE),
    re.compile(r"\bclass\b", re.IGNORECASE),
    re.compile(r"\bscript\b", re.IGNORECASE),
    re.compile(r"\bbug\b", re.IGNORECASE),
    re.compile(r"\berror\b", re.IGNORECASE),
    re.compile(r"\btraceback\b", re.IGNORECASE),
    re.compile(r"\bpytest\b", re.IGNORECASE),
    re.compile(r"\bunit tests?\b", re.IGNORECASE),
    re.compile(r"\brefactor\b", re.IGNORECASE),
    re.compile(r"\bimplement\b", re.IGNORECASE),
    re.compile(r"\bwrite a program\b", re.IGNORECASE),
    re.compile(r"\bpython\b", re.IGNORECASE),
    re.compile(r"\bjavascript\b", re.IGNORECASE),
    re.compile(r"\btypescript\b", re.IGNORECASE),
    re.compile(r"\bhtml\b", re.IGNORECASE),
    re.compile(r"\bcss\b", re.IGNORECASE),
    re.compile(r"\bsql\b", re.IGNORECASE),
    re.compile(r"\bapi\b", re.IGNORECASE),
    re.compile(r"\bcli\b", re.IGNORECASE),
    re.compile(r"\brepository\b", re.IGNORECASE),
    re.compile(r"\brepo\b", re.IGNORECASE),
    re.compile(r"\bfile edits?\b", re.IGNORECASE),
]


def has_obvious_coding_signal(goal: str) -> bool:
    """
    Return True if `goal` contains at least one obvious coding-task
    keyword or phrase from the fixed list above. This is a deterministic
    backstop, not a replacement for the Supervisor's own judgment -- see
    agents/supervisor.py's run(), which only uses this to prevent
    downgrading an obviously coding goal to a non-coding mode, never to
    upgrade an ambiguous one.
    """
    return any(pattern.search(goal) for pattern in _CODING_SIGNAL_PATTERNS)
