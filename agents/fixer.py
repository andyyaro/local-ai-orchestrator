"""
agents/fixer.py

The Fixer agent takes the original draft and the Critic's feedback,
then produces an improved revised draft that addresses every critique point.
"""

from agents.base_agent import BaseAgent


class FixerAgent(BaseAgent):

    def __init__(self, model: str, **kwargs):
        super().__init__(model=model, role="fixer", **kwargs)

    def run(self, goal: str, draft: str, critique: str, iteration: int = 1) -> str:
        """
        Produce a revised draft that addresses the critique.

        Args:
            goal:      The user's original goal statement.
            draft:     The draft to be improved.
            critique:  The structured critique from the Critic agent.
            iteration: Which revision pass this is (for prompt context).

        Returns:
            The full text of the revised draft.
        """
        system_prompt = self.load_prompt_template()

        full_prompt = f"""{system_prompt}

ORIGINAL GOAL:
{goal}

CURRENT DRAFT (revision {iteration}):
{draft}

CRITIC'S FEEDBACK:
{critique}

Now write the complete improved draft that addresses every issue raised above.
"""
        print(f"  [Fixer] Calling {self.model} (revision {iteration})...")
        result = self.call_model(full_prompt)
        print(f"  [Fixer] Revised draft complete ({len(result)} chars)")
        return result
