"""
agents/critic.py

The Critic agent reviews a draft against the original goal and produces
structured, actionable feedback. It does not rewrite — only critiques.
"""

from agents.base_agent import BaseAgent


class CriticAgent(BaseAgent):

    def __init__(self, model: str, **kwargs):
        super().__init__(model=model, role="critic", **kwargs)

    def run(self, goal: str, draft: str) -> str:
        """
        Critique the draft against the original goal.

        Args:
            goal: The user's original goal statement.
            draft: The draft text produced by the Builder.

        Returns:
            A structured critique as plain text.
        """
        system_prompt = self.load_prompt_template()

        full_prompt = f"""{system_prompt}

ORIGINAL GOAL:
{goal}

DRAFT TO REVIEW:
{draft}

Provide your critique now. Be specific and actionable.
"""
        print(f"  [Critic] Calling {self.model}...")
        result = self.call_model(full_prompt)
        print(f"  [Critic] Critique complete ({len(result)} chars)")
        return result
