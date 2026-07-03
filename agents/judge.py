"""
agents/judge.py

The Judge agent scores a draft against the original goal and returns
a structured JSON verdict. It decides whether the output passes the
quality threshold.

Expected JSON output format:
{
    "scores": {
        "completeness": 0-25,
        "accuracy": 0-25,
        "clarity": 0-25,
        "usefulness": 0-25
    },
    "total_score": 0-100,
    "pass": true/false,
    "hard_fails": [],
    "rationale": "One paragraph explaining the score."
}
"""

import json
import re
from agents.base_agent import BaseAgent


PASS_THRESHOLD = 70  # default; overridden by pipeline caller


class JudgeAgent(BaseAgent):

    def __init__(self, model: str, pass_threshold: int = PASS_THRESHOLD, **kwargs):
        super().__init__(model=model, role="judge", **kwargs)
        self.pass_threshold = pass_threshold

    def run(self, goal: str, draft: str, iteration: int = 1) -> dict:
        """
        Score the draft and return a verdict dict.

        Args:
            goal:      The user's original goal statement.
            draft:     The draft to be scored.
            iteration: Which iteration this is (for logging context).

        Returns:
            A dict matching the JSON schema above.
            On unrecoverable parse failure, returns a safe fallback dict.
        """
        system_prompt = self.load_prompt_template()

        full_prompt = f"""{system_prompt}

ORIGINAL GOAL:
{goal}

DRAFT TO SCORE (iteration {iteration}):
{draft}

Return ONLY the JSON object. No explanation, no markdown, no code fences.
The first character must be {{ and the final character must be }}.
"""
        print(f"  [Judge] Calling {self.model} (iteration {iteration})...")

        # Try up to 3 times to get valid JSON
        raw = ""
        for attempt in range(1, 4):
            raw = self.call_model(full_prompt)
            verdict = self._parse_json(raw)
            if verdict is not None:
                verdict = self._validate_and_fix(verdict)
                verdict["pass"] = verdict["total_score"] >= self.pass_threshold
                print(
                    f"  [Judge] Score: {verdict['total_score']}/100 "
                    f"({'PASS' if verdict['pass'] else 'FAIL'})"
                )
                return verdict
            print(f"  [Judge] Attempt {attempt}: could not parse JSON. Retrying...")

        # All attempts failed — return a conservative fallback
        print("  [Judge] WARNING: Could not parse Judge output after 3 attempts.")
        print(f"  [Judge] Raw output was:\n{raw[:500]}")
        return self._fallback_verdict(raw)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _parse_json(self, text: str) -> dict | None:
        """
        Try to extract a JSON object from the model's response.
        Handles clean JSON, markdown fences, leading/trailing text,
        and the common Bootstrap-model error of omitting the final closing brace.
        """
        candidates = []

        raw = text.strip()
        candidates.append(raw)

        # Strip markdown code fences and retry.
        stripped = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
        candidates.append(stripped)

        # Extract the substring between the first opening brace and the last
        # closing brace. This handles leading/trailing commentary.
        first_open = stripped.find("{")
        last_close = stripped.rfind("}")
        if first_open != -1 and last_close != -1 and last_close > first_open:
            candidates.append(stripped[first_open:last_close + 1])

        # If the model started a JSON object but forgot one or more final braces,
        # append only the number of braces needed to balance the object.
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
        """Return a parsed JSON dict, or None if parsing fails."""
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return None
        return None

    def _validate_and_fix(self, verdict: dict) -> dict:
        """
        Ensure required keys exist and values are in range.
        Fills in safe defaults for any missing fields.
        """
        # Ensure scores dict exists
        if "scores" not in verdict or not isinstance(verdict["scores"], dict):
            verdict["scores"] = {
                "completeness": 15,
                "accuracy": 15,
                "clarity": 15,
                "usefulness": 15,
            }

        # Clamp each score to 0–25
        for key in ["completeness", "accuracy", "clarity", "usefulness"]:
            if key not in verdict["scores"]:
                verdict["scores"][key] = 15
            verdict["scores"][key] = max(0, min(25, int(verdict["scores"].get(key, 15))))

        # Recompute total_score from individual scores (do not trust the model's sum)
        verdict["total_score"] = sum(verdict["scores"].values())

        # Ensure hard_fails is a list
        if "hard_fails" not in verdict or not isinstance(verdict["hard_fails"], list):
            verdict["hard_fails"] = []

        # Ensure rationale is a string
        if "rationale" not in verdict or not isinstance(verdict["rationale"], str):
            verdict["rationale"] = "No rationale provided."

        return verdict

    def _fallback_verdict(self, raw_text: str) -> dict:
        """
        Return a conservative failing verdict when JSON parsing fails entirely.
        Saves the raw output so you can inspect it.
        """
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
