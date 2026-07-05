"""
agents/supervisor.py

The Supervisor agent receives the raw user goal and returns a refined,
unambiguous problem statement plus a routing decision (which mode to use).
For the MVP, it returns the goal with light cleanup and defaults to "general".
"""

from agents.base_agent import BaseAgent
from orchestrator.mode_classifier import has_obvious_coding_signal


class SupervisorAgent(BaseAgent):

    def __init__(self, model: str, **kwargs):
        super().__init__(model=model, role="supervisor", **kwargs)

    def run(self, goal: str) -> dict:
        """
        Refine the user goal and determine workflow mode.

        Returns:
            dict with keys: refined_goal (str), mode (str)
        """
        system_prompt = self.load_prompt_template()

        full_prompt = f"""{system_prompt}

USER'S RAW GOAL:
{goal}

Return your response as two clearly labeled sections:
REFINED GOAL: <one clear problem statement>
MODE: <one of: writing, coding, planning, debugging, study, general>
"""
        print(f"  [Supervisor] Calling {self.model}...")
        raw = self.call_model(full_prompt)

        refined_goal = goal  # fallback
        mode = "general"

        for line in raw.splitlines():
            if line.upper().startswith("REFINED GOAL:"):
                refined_goal = line.split(":", 1)[1].strip()
            elif line.upper().startswith("MODE:"):
                mode_raw = line.split(":", 1)[1].strip().lower()
                if mode_raw in {"writing", "coding", "planning",
                                "debugging", "study", "general"}:
                    mode = mode_raw

        # Phase 12b: deterministic backstop. The Supervisor's own
        # LLM-based mode classification can misclassify an unambiguous
        # coding goal (verified against a real run: "Write a Python
        # function called double(n)..." was classified mode="general").
        # If the user's raw goal contains an obvious coding signal and
        # the model didn't already pick a coding-adjacent mode, force
        # "coding" rather than silently downgrading it. Checked against
        # the original goal, not refined_goal, since the model's own
        # rephrasing is exactly what can drop the signal in the first
        # place (mirroring the original-vs-refined precedent already
        # established for hard-constraint preservation).
        if mode not in {"coding", "debugging"} and has_obvious_coding_signal(goal):
            print(f"  [Supervisor] Overriding mode '{mode}' -> 'coding' "
                  "(deterministic coding-signal guardrail)")
            mode = "coding"

        print(f"  [Supervisor] Mode: {mode} | Goal: {refined_goal[:80]}")
        return {"refined_goal": refined_goal, "mode": mode}
