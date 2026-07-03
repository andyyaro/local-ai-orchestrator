from agents.base_agent import BaseAgent


class BuilderAgent(BaseAgent):

    def __init__(self, model: str, **kwargs):
        super().__init__(model=model, role="builder", **kwargs)

    def run(self, goal: str, plan: str, mode: str = "general") -> str:
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

PLAN TO FOLLOW:
{plan}

Now write the complete deliverable according to the plan above.
"""
        print(f"  [Builder] Calling {self.model} (mode: {mode})...")
        result = self.call_model(full_prompt)
        print(f"  [Builder] Draft complete ({len(result)} chars)")
        return result
