"""
agents/supervisor.py

The Supervisor agent receives the raw user goal and returns a refined,
unambiguous problem statement plus a routing decision (which mode to use).
For the MVP, it returns the goal with light cleanup and defaults to "general".
"""

from agents.base_agent import BaseAgent


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

        print(f"  [Supervisor] Mode: {mode} | Goal: {refined_goal[:80]}")
        return {"refined_goal": refined_goal, "mode": mode}
