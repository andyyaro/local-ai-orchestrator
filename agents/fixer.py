from agents.base_agent import BaseAgent


class FixerAgent(BaseAgent):

    def __init__(self, model: str, **kwargs):
        super().__init__(model=model, role="fixer", **kwargs)

    def run(self, goal: str, draft: str, critique: str,
            iteration: int = 1, mode: str = "general") -> str:
        from orchestrator.modes import get_prompt_suffix, get_output_format

        system_prompt = self.load_prompt_template()
        suffix = get_prompt_suffix(mode)
        output_format = get_output_format(mode)

        full_prompt = f"""{system_prompt}

{suffix}

EXPECTED OUTPUT FORMAT:
{output_format}

GOAL:
{goal}

CURRENT DRAFT (revision {iteration}):
{draft}

FEEDBACK:
{critique}

Revise the draft using the feedback and keep the result aligned with the goal.
"""
        print(f"  [Fixer] Calling {self.model} (revision {iteration}, mode: {mode})...")
        result = self.call_model(full_prompt)
        print(f"  [Fixer] Revised draft complete ({len(result)} chars)")
        return result
