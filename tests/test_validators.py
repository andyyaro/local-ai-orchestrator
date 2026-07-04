from orchestrator.validators import (
    apply_validator_results_to_verdict,
    check_bullet_count,
    check_code_block_presence,
    check_forbidden_phrases,
    check_json_schema,
    check_required_sections,
    check_word_limit,
    count_words,
    extract_word_limit,
    run_validators,
    should_break_on_hard_fail,
)


# ── extract_word_limit ────────────────────────────────────────────────────────

def test_extract_word_limit_exactly_120_words():
    assert extract_word_limit(
        "Write a summary of the water cycle in exactly 120 words."
    ) == (120, "exact")


def test_extract_word_limit_bare_number_defaults_to_exact():
    assert extract_word_limit("Write a summary in 120 words.") == (120, "exact")


def test_extract_word_limit_no_more_than():
    assert extract_word_limit(
        "Write an essay of no more than 500 words about decorators."
    ) == (500, "max")


def test_extract_word_limit_at_least():
    assert extract_word_limit(
        "Write at least 50 words explaining recursion."
    ) == (50, "min")


def test_extract_word_limit_hyphenated_form():
    assert extract_word_limit(
        "Write a 300-word guide to Python decorators."
    ) == (300, "exact")


def test_extract_word_limit_returns_none_when_absent():
    assert extract_word_limit(
        "Write a comprehensive guide to Python decorators."
    ) == (None, None)


# ── count_words ────────────────────────────────────────────────────────────────

def test_count_words_known_string():
    assert count_words("one two three four five") == 5


def test_count_words_empty_string():
    assert count_words("") == 0


# ── check_word_limit ────────────────────────────────────────────────────────────

def test_check_word_limit_exact_fails_far_outside_tolerance():
    draft = " ".join(["word"] * 300)
    result = check_word_limit(draft, limit=120, mode="exact", tolerance=12)
    assert result.passed is False
    assert result.rule == "word_limit"


def test_check_word_limit_exact_passes_within_tolerance():
    draft = " ".join(["word"] * 126)
    result = check_word_limit(draft, limit=120, mode="exact", tolerance=12)
    assert result.passed is True


def test_check_word_limit_max_boundary():
    draft = " ".join(["word"] * 500)
    assert check_word_limit(draft, limit=500, mode="max").passed is True
    draft_over = " ".join(["word"] * 501)
    assert check_word_limit(draft_over, limit=500, mode="max").passed is False


def test_check_word_limit_min_boundary():
    draft = " ".join(["word"] * 50)
    assert check_word_limit(draft, limit=50, mode="min").passed is True
    draft_under = " ".join(["word"] * 49)
    assert check_word_limit(draft_under, limit=50, mode="min").passed is False


# ── check_required_sections ─────────────────────────────────────────────────────

def test_check_required_sections_pass():
    draft = "## Introduction\ntext\n## Conclusion\nmore text"
    result = check_required_sections(draft, ["Introduction", "Conclusion"])
    assert result.passed is True


def test_check_required_sections_fail():
    draft = "## Introduction\ntext"
    result = check_required_sections(draft, ["Introduction", "Conclusion"])
    assert result.passed is False
    assert "Conclusion" in result.detail


# ── check_forbidden_phrases ──────────────────────────────────────────────────────

def test_check_forbidden_phrases_pass():
    result = check_forbidden_phrases("A clean, helpful answer.", ["as an AI language model"])
    assert result.passed is True


def test_check_forbidden_phrases_fail():
    result = check_forbidden_phrases(
        "As an AI language model, I cannot help with that.",
        ["as an AI language model"],
    )
    assert result.passed is False


# ── check_bullet_count ───────────────────────────────────────────────────────────

def test_check_bullet_count_pass():
    draft = "- one\n- two\n- three"
    result = check_bullet_count(draft, min_bullets=2, max_bullets=5)
    assert result.passed is True


def test_check_bullet_count_fail_too_few():
    draft = "- one"
    result = check_bullet_count(draft, min_bullets=3)
    assert result.passed is False


def test_check_bullet_count_fail_too_many():
    draft = "\n".join(f"- item {i}" for i in range(10))
    result = check_bullet_count(draft, max_bullets=5)
    assert result.passed is False


# ── check_json_schema ──────────────────────────────────────────────────────────

def test_check_json_schema_pass_with_fenced_json():
    draft = '```json\n{"scores": {"a": 1}, "total_score": 80}\n```'
    result = check_json_schema(draft, required_keys=["scores", "total_score"])
    assert result.passed is True


def test_check_json_schema_fail_missing_key():
    draft = '{"scores": {"a": 1}}'
    result = check_json_schema(draft, required_keys=["scores", "total_score"])
    assert result.passed is False
    assert "total_score" in result.detail


def test_check_json_schema_fail_unparsable():
    result = check_json_schema("not json at all", required_keys=["scores"])
    assert result.passed is False


# ── check_code_block_presence ───────────────────────────────────────────────────

def test_check_code_block_presence_required_and_present():
    draft = "Here is the code:\n```python\nprint('hi')\n```"
    assert check_code_block_presence(draft, required=True).passed is True


def test_check_code_block_presence_required_but_missing():
    assert check_code_block_presence("Just prose, no code.", required=True).passed is False


def test_check_code_block_presence_not_required_and_absent():
    assert check_code_block_presence("Just prose, no code.", required=False).passed is True


def test_check_code_block_presence_not_required_but_present():
    draft = "```python\nprint('hi')\n```"
    assert check_code_block_presence(draft, required=False).passed is False


# ── run_validators ───────────────────────────────────────────────────────────────

def test_run_validators_empty_when_no_constraints_detected():
    results = run_validators(
        goal="Write a comprehensive guide to Python decorators.",
        draft="Some draft text.",
        mode="writing",
    )
    assert results == []


def test_run_validators_flags_word_limit_violation():
    goal = "Write a summary of the water cycle in exactly 120 words."
    draft = " ".join(["word"] * 300)
    results = run_validators(goal=goal, draft=draft, mode="writing")
    assert len(results) == 1
    assert results[0].rule == "word_limit"
    assert results[0].passed is False


def test_run_validators_checks_code_block_presence_in_coding_mode():
    results = run_validators(
        goal="Write a function that adds two numbers.",
        draft="Just prose, no code block here.",
        mode="coding",
    )
    rules = {r.rule: r for r in results}
    assert "code_block_presence" in rules
    assert rules["code_block_presence"].passed is False


# ── Regression test: the original 120-word bug ──────────────────────────────────

def test_regression_120_word_goal_with_300_word_draft_fails_validation():
    goal = "Write a summary of why sleep deprivation hurts productivity in exactly 120 words."
    draft = " ".join(["word"] * 300)

    results = run_validators(goal=goal, draft=draft, mode="writing")

    word_limit_results = [r for r in results if r.rule == "word_limit"]
    assert len(word_limit_results) == 1
    assert word_limit_results[0].passed is False


# ── apply_validator_results_to_verdict ─────────────────────────────────────────

def test_apply_validator_results_forces_hard_fail_on_failure():
    verdict = {
        "scores": {"completeness": 25, "accuracy": 25, "clarity": 20, "usefulness": 15},
        "total_score": 85,
        "pass": True,
        "hard_fails": [],
        "rationale": "Looked good.",
    }
    failing = [check_word_limit(" ".join(["word"] * 300), limit=120, mode="exact", tolerance=12)]

    result = apply_validator_results_to_verdict(verdict, failing)

    assert result["pass"] is False
    assert result["total_score"] == 0
    assert "constraint_violation" in result["hard_fails"]
    assert "word_limit" in result["validator_failures"]


def test_apply_validator_results_leaves_verdict_unchanged_when_all_pass():
    verdict = {
        "scores": {"completeness": 25, "accuracy": 25, "clarity": 20, "usefulness": 15},
        "total_score": 85,
        "pass": True,
        "hard_fails": [],
        "rationale": "Looked good.",
    }
    passing = [check_word_limit(" ".join(["word"] * 120), limit=120, mode="exact", tolerance=12)]

    result = apply_validator_results_to_verdict(verdict, passing)

    assert result["pass"] is True
    assert result["total_score"] == 85
    assert result["hard_fails"] == []
    assert "validator_failures" not in result


# ── Regression test: Phase 6b Supervisor-drops-constraint bug ──────────────────

def test_run_validators_uses_original_goal_when_refined_goal_drops_constraint():
    """
    The Phase 6b bug: the Supervisor's refined_goal can drop a hard
    constraint the user actually stated (e.g. rewriting "50-word summary"
    into an unconstrained restatement). run_validators must still catch
    this by checking original_goal, the user's literal text, rather than
    only the refined paraphrase that lost the constraint.
    """
    original_goal = "Write a 50-word summary of why sleep matters."
    refined_goal_that_dropped_the_constraint = (
        "Explain the physiological and psychological importance of sleep "
        "in humans, with specific examples of how lack of sleep affects "
        "cognitive function."
    )
    long_draft = " ".join(["word"] * 300)

    results = run_validators(
        refined_goal_that_dropped_the_constraint,
        long_draft,
        mode="writing",
        original_goal=original_goal,
    )

    word_limit_results = [r for r in results if r.rule == "word_limit"]
    assert len(word_limit_results) == 1
    assert word_limit_results[0].passed is False


def test_run_validators_without_original_goal_keeps_old_behavior():
    """original_goal is optional -- omitting it must behave exactly as
    before (extract constraints from `goal` itself), so existing callers
    of run_validators(goal=..., draft=..., mode=...) are unaffected."""
    results = run_validators(
        goal="Write a comprehensive guide to Python decorators.",
        draft="Some draft text.",
        mode="writing",
    )
    assert results == []


def test_regression_120_word_verdict_cannot_pass_the_judge():
    """
    The exact end-to-end regression this phase exists to fix: a Judge that
    scored a 300-word draft highly against a 120-word-exact goal must have
    its verdict forced to fail once the deterministic validator runs.
    """
    goal = "Write a summary of the water cycle in exactly 120 words."
    draft = " ".join(["word"] * 300)

    judge_verdict = {
        "scores": {"completeness": 25, "accuracy": 25, "clarity": 20, "usefulness": 15},
        "total_score": 85,
        "pass": True,
        "hard_fails": [],
        "rationale": "Comprehensive and well written.",
    }

    validator_results = run_validators(goal=goal, draft=draft, mode="writing")
    final_verdict = apply_validator_results_to_verdict(judge_verdict, validator_results)

    assert final_verdict["pass"] is False
    assert "constraint_violation" in final_verdict["hard_fails"]


# ── should_break_on_hard_fail: Phase 6c repair-vs-stop decisions ────────────────

def test_should_break_on_hard_fail_returns_false_when_no_hard_fails():
    verdict = {"hard_fails": []}
    assert should_break_on_hard_fail("writing", verdict, iteration=1, max_loops=3) is False


def test_should_break_on_hard_fail_continues_for_constraint_violation_alone_with_iterations_remaining():
    verdict = {"hard_fails": ["constraint_violation"]}
    assert should_break_on_hard_fail("writing", verdict, iteration=1, max_loops=3) is False


def test_should_break_on_hard_fail_stops_for_constraint_violation_when_max_loops_reached():
    verdict = {"hard_fails": ["constraint_violation"]}
    assert should_break_on_hard_fail("writing", verdict, iteration=3, max_loops=3) is True


def test_should_break_on_hard_fail_stops_when_unknown_hard_fail_present_alongside_constraint_violation():
    """
    constraint_violation alone is repairable, but a run must never silently
    keep looping on a hard fail it doesn't know how to repair -- if some
    other, unrecognized hard fail is present too, stop immediately as
    before, regardless of how many iterations remain.
    """
    verdict = {"hard_fails": ["constraint_violation", "some_other_reason"]}
    assert should_break_on_hard_fail("writing", verdict, iteration=1, max_loops=3) is True


# ── should_break_on_hard_fail: coding-mode broken_code carve-out is unchanged ───
#
# Phase 6c must not weaken the existing broken_code behavior: it continues
# until max_loops in coding mode regardless of what else is in hard_fails,
# exactly as before this phase.

def test_should_break_on_hard_fail_continues_for_broken_code_in_coding_mode_when_iterations_remain():
    verdict = {"hard_fails": ["broken_code"]}
    assert should_break_on_hard_fail("coding", verdict, iteration=1, max_loops=3) is False


def test_should_break_on_hard_fail_stops_for_broken_code_when_max_loops_reached():
    verdict = {"hard_fails": ["broken_code"]}
    assert should_break_on_hard_fail("coding", verdict, iteration=3, max_loops=3) is True


def test_should_break_on_hard_fail_continues_for_broken_code_alongside_constraint_violation_in_coding_mode():
    verdict = {"hard_fails": ["broken_code", "constraint_violation"]}
    assert should_break_on_hard_fail("coding", verdict, iteration=1, max_loops=3) is False


def test_should_break_on_hard_fail_stops_for_broken_code_outside_coding_mode():
    """broken_code's carve-out is coding-mode-only -- outside coding mode
    it is an unrecognized hard fail and stops immediately, same as before."""
    verdict = {"hard_fails": ["broken_code"]}
    assert should_break_on_hard_fail("writing", verdict, iteration=1, max_loops=3) is True
