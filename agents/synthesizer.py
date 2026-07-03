"""
agents/synthesizer.py

The Final Synthesizer polishes the best-scoring draft into a clean,
presentation-ready final output.
"""

from agents.base_agent import BaseAgent


class SynthesizerAgent(BaseAgent):

    def __init__(self, model: str, **kwargs):
        super().__init__(model=model, role="synthesizer", **kwargs)

    def run(self, goal: str, best_draft: str, score: int,
            iterations: int) -> str:
        """
        Polish the best draft into the final deliverable.

        Args:
            goal:       The original user goal.
            best_draft: The highest-scoring draft from the loop.
            score:      The score of the best draft.
            iterations: How many loop iterations were completed.

        Returns:
            The polished final output as a string.
        """
        system_prompt = self.load_prompt_template()

        full_prompt = f"""{system_prompt}

ORIGINAL GOAL:
{goal}

BEST DRAFT (score {score}/100 after {iterations} iteration(s)):
{best_draft}

Polish this draft into the final, presentation-ready deliverable now.
"""
        print(f"  [Synthesizer] Calling {self.model}...")
        result = self.call_model(full_prompt)
        print(f"  [Synthesizer] Final output complete ({len(result)} chars)")
        return result
