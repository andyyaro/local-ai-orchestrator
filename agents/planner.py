"""
agents/planner.py

The Planner agent receives the refined goal and produces a step-by-step
plan that the Builder will follow.
"""

from agents.base_agent import BaseAgent


class PlannerAgent(BaseAgent):

    def __init__(self, model: str, **kwargs):
        super().__init__(model=model, role="planner", **kwargs)

    def run(self, goal: str, mode: str = "general") -> str:
        """
        Produce a structured plan for the Builder to follow.

        Args:
            goal: The refined goal from the Supervisor.
            mode: Workflow mode (writing, coding, planning, etc.)

        Returns:
            A numbered plan as plain text.
        """
        system_prompt = self.load_prompt_template()

        full_prompt = f"""{system_prompt}

REFINED GOAL:
{goal}

MODE: {mode}

Produce the step-by-step plan now. Number each step. Be specific.
"""
        print(f"  [Planner] Calling {self.model}...")
        result = self.call_model(full_prompt)
        print(f"  [Planner] Plan complete ({len(result)} chars)")
        return result
