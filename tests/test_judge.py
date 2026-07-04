from agents.judge import JudgeAgent


def make_judge():
    return JudgeAgent(model="dummy-model", pass_threshold=70)


def test_parse_json_from_markdown_fence():
    judge = make_judge()

    raw = """```json
{
  "scores": {
    "completeness": 20,
    "accuracy": 20,
    "clarity": 20,
    "usefulness": 20
  },
  "hard_fails": [],
  "rationale": "Good draft."
}
```"""

    parsed = judge._parse_json(raw)
    fixed = judge._validate_and_fix(parsed)

    assert fixed["total_score"] == 80
    assert fixed["hard_fails"] == []
    assert fixed["rationale"] == "Good draft."


def test_parse_json_from_extra_text():
    judge = make_judge()

    raw = """
The answer is below:
{
  "scores": {
    "completeness": 18,
    "accuracy": 17,
    "clarity": 16,
    "usefulness": 15
  },
  "hard_fails": [],
  "rationale": "Parsed from noisy output."
}
Thanks.
"""

    parsed = judge._parse_json(raw)
    fixed = judge._validate_and_fix(parsed)

    assert fixed["total_score"] == 66
    assert fixed["rationale"] == "Parsed from noisy output."


def test_validate_and_fix_clamps_scores_and_adds_defaults():
    judge = make_judge()

    verdict = {
        "scores": {
            "completeness": 99,
            "accuracy": -5,
            "clarity": 10,
        },
        "hard_fails": "not-a-list",
    }

    fixed = judge._validate_and_fix(verdict)

    assert fixed["scores"]["completeness"] == 25
    assert fixed["scores"]["accuracy"] == 0
    assert fixed["scores"]["clarity"] == 10
    assert fixed["scores"]["usefulness"] == 15
    assert fixed["total_score"] == 50
    assert fixed["hard_fails"] == []
    assert fixed["rationale"] == "No rationale provided."


def test_fallback_verdict_is_failure():
    judge = make_judge()

    verdict = judge._fallback_verdict("bad model output")

    assert verdict["total_score"] == 40
    assert verdict["pass"] is False
    assert "judge_parse_error" in verdict["hard_fails"]
    assert verdict["raw_judge_output"] == "bad model output"
