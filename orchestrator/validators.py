"""
orchestrator/validators.py

Deterministic, non-LLM constraint checks that run before the Judge's verdict
is accepted. Word counts and other checkable constraints are deterministic
operations and belong in code, not in a model's judgment -- the Judge is not
trusted to notice them reliably.
"""

import json
import re
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of a single deterministic constraint check."""
    rule: str
    passed: bool
    detail: str


# Word-count tolerance for "exact" mode, as a fraction of the requested
# count. Natural-language generation rarely lands on the literal number, so
# some slack is needed -- 10% keeps a genuinely long draft (e.g. 300 words
# against a 120-word ask) failing while not punishing a 126-word draft
# against "exactly 120 words".
EXACT_TOLERANCE_FRACTION = 0.10

# Checked in order of specificity: qualified phrasings ("no more than",
# "at least", "exactly") are matched before the bare "<number> words"
# fallback, so "no more than 500 words" is classified as "max" rather than
# falling through to the generic exact-number pattern.
_WORD_LIMIT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(?:no more than|at most|maximum of|up to)\s+(\d+)\s+words?\b", re.IGNORECASE), "max"),
    (re.compile(r"\b(?:at least|minimum of|no fewer than)\s+(\d+)\s+words?\b", re.IGNORECASE), "min"),
    (re.compile(r"\bexactly\s+(\d+)\s+words?\b", re.IGNORECASE), "exact"),
    (re.compile(r"\b(\d+)-word\b", re.IGNORECASE), "exact"),
    (re.compile(r"\b(\d+)\s+words?\b", re.IGNORECASE), "exact"),
]

_BULLET_LINE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+", re.MULTILINE)


def extract_word_limit(goal: str) -> tuple[int | None, str | None]:
    """
    Parse a goal string for a word-count constraint.

    Returns (limit, mode) where mode is "exact", "max", or "min", or
    (None, None) if no constraint was found. This is a plain regex search --
    no model call is involved.
    """
    for pattern, mode in _WORD_LIMIT_PATTERNS:
        match = pattern.search(goal)
        if match:
            return int(match.group(1)), mode
    return None, None


def count_words(text: str) -> int:
    """
    Count words by splitting on whitespace. This is an approximation, not
    true tokenization: hyphenated words and contractions each count as one
    word, matching how a person would casually count them.
    """
    return len(text.split())


def check_word_limit(draft: str, limit: int, mode: str, tolerance: int = 0) -> ValidationResult:
    """
    Compare the draft's word count against `limit` according to `mode`.

    "max" and "min" are hard boundaries with no slack. "exact" allows a
    caller-supplied tolerance band, since natural-language generation rarely
    lands on the literal requested number.
    """
    actual = count_words(draft)

    if mode == "max":
        passed = actual <= limit
        detail = (
            f"word count {actual} is within maximum {limit}"
            if passed else f"word count {actual} exceeds maximum {limit}"
        )
    elif mode == "min":
        passed = actual >= limit
        detail = (
            f"word count {actual} meets minimum {limit}"
            if passed else f"word count {actual} is below minimum {limit}"
        )
    elif mode == "exact":
        passed = abs(actual - limit) <= tolerance
        detail = (
            f"word count {actual} is within the {tolerance}-word tolerance of "
            f"exact target {limit}"
            if passed else
            f"word count {actual} is outside the {tolerance}-word tolerance "
            f"for exact target {limit}"
        )
    else:
        passed = False
        detail = f"unknown word-limit mode '{mode}'"

    return ValidationResult(rule="word_limit", passed=passed, detail=detail)


def check_required_sections(draft: str, required: list[str]) -> ValidationResult:
    """Confirm each required heading or keyword appears in the draft (case-insensitive)."""
    draft_lower = draft.lower()
    missing = [item for item in required if item.lower() not in draft_lower]
    passed = not missing
    detail = (
        "all required sections present" if passed
        else f"missing required section(s): {', '.join(missing)}"
    )
    return ValidationResult(rule="required_sections", passed=passed, detail=detail)


def check_forbidden_phrases(draft: str, forbidden: list[str]) -> ValidationResult:
    """Confirm none of the forbidden phrases appear in the draft (case-insensitive)."""
    draft_lower = draft.lower()
    found = [phrase for phrase in forbidden if phrase.lower() in draft_lower]
    passed = not found
    detail = (
        "no forbidden phrases found" if passed
        else f"forbidden phrase(s) present: {', '.join(found)}"
    )
    return ValidationResult(rule="forbidden_phrases", passed=passed, detail=detail)


def check_bullet_count(
    draft: str, min_bullets: int | None = None, max_bullets: int | None = None
) -> ValidationResult:
    """Count lines starting with '-', '*', or a numbered list marker, against bounds."""
    count = len(_BULLET_LINE.findall(draft))

    if min_bullets is not None and count < min_bullets:
        return ValidationResult(
            rule="bullet_count", passed=False,
            detail=f"found {count} bullet(s), fewer than minimum {min_bullets}",
        )
    if max_bullets is not None and count > max_bullets:
        return ValidationResult(
            rule="bullet_count", passed=False,
            detail=f"found {count} bullet(s), more than maximum {max_bullets}",
        )
    return ValidationResult(
        rule="bullet_count", passed=True,
        detail=f"bullet count {count} within bounds",
    )


def _try_parse_json(text: str) -> dict | None:
    """
    Forgiving JSON extraction mirroring agents/judge.py's _parse_json
    approach (strip code fences, try the raw text, then the widest
    first-brace/last-brace slice) without importing from the agent layer.
    """
    candidates = [text.strip()]

    stripped = re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()
    candidates.append(stripped)

    first_open = stripped.find("{")
    last_close = stripped.rfind("}")
    if first_open != -1 and last_close != -1 and last_close > first_open:
        candidates.append(stripped[first_open:last_close + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def check_json_schema(draft: str, required_keys: list[str]) -> ValidationResult:
    """Confirm the draft parses as a JSON object containing every required top-level key."""
    parsed = _try_parse_json(draft)
    if parsed is None:
        return ValidationResult(
            rule="json_schema", passed=False,
            detail="draft could not be parsed as a JSON object",
        )

    missing = [key for key in required_keys if key not in parsed]
    passed = not missing
    detail = (
        "all required JSON keys present" if passed
        else f"missing required JSON key(s): {', '.join(missing)}"
    )
    return ValidationResult(rule="json_schema", passed=passed, detail=detail)


def check_code_block_presence(draft: str, required: bool) -> ValidationResult:
    """Confirm a fenced code block is present (or absent) as required."""
    has_code_block = "```" in draft

    if required:
        passed = has_code_block
        detail = (
            "fenced code block present" if passed
            else "no fenced code block found, but one is required"
        )
    else:
        passed = not has_code_block
        detail = (
            "no fenced code block present, as expected" if passed
            else "a fenced code block was found but none was expected"
        )
    return ValidationResult(rule="code_block_presence", passed=passed, detail=detail)


def run_validators(
    goal: str, draft: str, mode: str, *, original_goal: str | None = None
) -> list[ValidationResult]:
    """
    Run every constraint check applicable to this goal/mode and return the
    full list of results (not just failures), so passing checks can be
    logged too.

    Word-limit enforcement is applied whenever the goal text contains a
    recognizable word-count constraint. Code-block presence is enforced only
    in coding mode. required_sections/forbidden_phrases/bullet_count/
    json_schema are available for callers with task-specific constraints to
    check but are not auto-invoked here, since there is no existing
    per-task configuration surface describing what those constraints should
    be for an arbitrary goal.

    `original_goal`, if given, is the user's raw goal text before Supervisor
    refinement, and is used instead of `goal` for word-limit extraction.
    This exists because the Supervisor's refined goal is not guaranteed to
    preserve hard constraints the user actually stated (e.g. "50-word
    summary" can get rewritten into an unconstrained restatement) -- the
    original goal is the authoritative source for a stated constraint, so
    it must be checked directly rather than trusting a refined paraphrase.
    """
    results: list[ValidationResult] = []

    constraint_source = original_goal if original_goal is not None else goal
    limit, limit_mode = extract_word_limit(constraint_source)
    if limit is not None:
        tolerance = (
            max(1, round(limit * EXACT_TOLERANCE_FRACTION))
            if limit_mode == "exact" else 0
        )
        results.append(check_word_limit(draft, limit, limit_mode, tolerance=tolerance))

    if mode == "coding":
        results.append(check_code_block_presence(draft, required=True))

    return results


def apply_validator_results_to_verdict(verdict: dict, validator_results: list[ValidationResult]) -> dict:
    """
    Force a hard fail when any deterministic constraint check fails, the same
    way orchestrator/code_runner.py's verification overrides the Judge for
    broken code. A high Judge score cannot rescue a draft that violates a
    checkable constraint such as a word limit.

    Shared by both run.py and orchestrator/graph.py so the two pipelines
    apply identical constraint enforcement rather than each maintaining a
    separate copy of this logic.
    """
    failed = [r for r in validator_results if not r.passed]
    if not failed:
        return verdict

    hard_fails = verdict.get("hard_fails", [])
    if not isinstance(hard_fails, list):
        hard_fails = []
    if "constraint_violation" not in hard_fails:
        hard_fails.append("constraint_violation")

    verdict["hard_fails"] = hard_fails
    verdict["pass"] = False
    verdict["total_score"] = min(verdict.get("total_score", 0), 0)
    detail = "; ".join(r.detail for r in failed)
    verdict["rationale"] = (
        str(verdict.get("rationale", ""))
        + "\n\nDeterministic constraint check failed before Judge pass/fail "
        + f"was accepted: {detail}"
    ).strip()
    verdict["validator_failures"] = [r.rule for r in failed]
    print(f"  [Validators] Hard fail: constraint_violation overrides Judge score ({detail})")
    return verdict
