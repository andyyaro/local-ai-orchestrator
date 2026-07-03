"""
agents/builder.py

The Builder agent creates the first draft of the deliverable.
It receives the goal and the planner's outline, and produces a full draft.
"""

from agents.base_agent import BaseAgent


class BuilderAgent(BaseAgent):

    def __init__(self, model: str, **kwargs):
        super().__init__(model=model, role="builder", **kwargs)

    def run(self, goal: str, plan: str) -> str:
        """
        Build a first draft based on the goal and plan.

        Args:
            goal: The user's original goal statement.
            plan: The structured plan from the Planner agent.

        Returns:
            The full text of the first draft.
        """
        system_prompt = self.load_prompt_template()

        full_prompt = f"""{system_prompt}

USER GOAL:
{goal}

PLAN TO FOLLOW:
{plan}

Now write the complete deliverable according to the plan above.
"""
        print(f"  [Builder] Calling {self.model}...")
        result = self.call_model(full_prompt)
        print(f"  [Builder] Draft complete ({len(result)} chars)")
        return result
