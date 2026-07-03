import json
import re
from agents.base_agent import BaseAgent


PASS_THRESHOLD = 70
DEFAULT_WEIGHTS = {
    "completeness": 25,
    "accuracy": 25,
    "clarity": 25,
    "usefulness": 25,
}


class JudgeAgent(BaseAgent):

    def __init__(self, model: str, pass_threshold: int = PASS_THRESHOLD, **kwargs):
        super().__init__(model=model, role="judge", **kwargs)
        self.pass_threshold = pass_threshold

    def run(self, goal: str, draft: str, iteration: int = 1,
            mode: str = "general") -> dict:
        from orchestrator.modes import get_judge_note, get_scoring_weights

        system_prompt = self.load_prompt_template()
        judge_note = get_judge_note(mode)
        weights = get_scoring_weights(mode)

        full_prompt = f"""{system_prompt}

MODE-SPECIFIC INSTRUCTION:
{judge_note}

SCORING WEIGHTS FOR THIS MODE:
- completeness : {weights['completeness']} points max
- accuracy     : {weights['accuracy']} points max
- clarity      : {weights['clarity']} points max
- usefulness   : {weights['usefulness']} points max
Total: 100 points

GOAL:
{goal}

DRAFT TO SCORE (iteration {iteration}):
{draft}

Return ONLY the JSON object. No explanation, no markdown, no code fences.
The first character must be {{ and the final character must be }}.
"""
        print(f"  [Judge] Calling {self.model} (iteration {iteration}, mode: {mode})...")

        raw = ""
        for attempt in range(1, 4):
            raw = self.call_model(full_prompt)
            verdict = self._parse_json(raw)
            if verdict is not None:
                verdict = self._validate_and_fix(verdict, weights)
                verdict["pass"] = verdict["total_score"] >= self.pass_threshold
                print(
                    f"  [Judge] Score: {verdict['total_score']}/100 "
                    f"({'PASS' if verdict['pass'] else 'FAIL'})"
                )
                return verdict
            print(f"  [Judge] Attempt {attempt}: could not parse JSON. Retrying...")

        print("  [Judge] WARNING: Could not parse Judge output after 3 attempts.")
        print(f"  [Judge] Raw output was:\n{raw[:500]}")
        return self._fallback_verdict(raw)

    def _parse_json(self, text: str) -> dict | None:
        candidates = []
        raw = text.strip()
        candidates.append(raw)

        stripped = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
        candidates.append(stripped)

        first_open = stripped.find("{")
        last_close = stripped.rfind("}")
        if first_open != -1 and last_close != -1 and last_close > first_open:
            candidates.append(stripped[first_open:last_close + 1])

        if first_open != -1:
            possible = stripped[first_open:]
            open_count = possible.count("{")
            close_count = possible.count("}")
            if open_count > close_count:
                candidates.append(possible + ("}" * (open_count - close_count)))

        for candidate in candidates:
            verdict = self._try_load_json(candidate)
            if verdict is not None:
                return verdict

        return None

    def _try_load_json(self, candidate: str) -> dict | None:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return None
        return None

    def _validate_and_fix(self, verdict: dict, weights: dict | None = None) -> dict:
        weights = weights or DEFAULT_WEIGHTS

        if "scores" not in verdict or not isinstance(verdict["scores"], dict):
            verdict["scores"] = {
                "completeness": min(15, weights.get("completeness", 25)),
                "accuracy": min(15, weights.get("accuracy", 25)),
                "clarity": min(15, weights.get("clarity", 25)),
                "usefulness": min(15, weights.get("usefulness", 25)),
            }

        for key in ["completeness", "accuracy", "clarity", "usefulness"]:
            if key not in verdict["scores"]:
                verdict["scores"][key] = min(15, weights.get(key, 25))
            max_points = int(weights.get(key, 25))
            verdict["scores"][key] = max(0, min(max_points, int(verdict["scores"].get(key, 0))))

        verdict["total_score"] = sum(verdict["scores"].values())

        if "hard_fails" not in verdict or not isinstance(verdict["hard_fails"], list):
            verdict["hard_fails"] = []

        if "rationale" not in verdict or not isinstance(verdict["rationale"], str):
            verdict["rationale"] = "No rationale provided."

        return verdict

    def _fallback_verdict(self, raw_text: str) -> dict:
        return {
            "scores": {
                "completeness": 10,
                "accuracy": 10,
                "clarity": 10,
                "usefulness": 10,
            },
            "total_score": 40,
            "pass": False,
            "hard_fails": ["judge_parse_error"],
            "rationale": (
                "The Judge agent returned output that could not be parsed as JSON. "
                "This is treated as a failing score. Raw output saved for inspection."
            ),
            "raw_judge_output": raw_text[:2000],
        }
