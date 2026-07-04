"""
agents/base_agent.py

Base class for all pipeline agents. Provides shared model-call logic,
prompt template loading, and error handling. All agent classes inherit from
BaseAgent and override the run() method.
"""

from pathlib import Path


PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class BaseAgent:
    """Shared foundation for all pipeline agents."""

    def __init__(self, model: str, role: str, temperature: float = 0.7,
                 num_ctx: int = 4096, max_retries: int = 2):
        self.model = model
        self.role = role
        self.temperature = temperature
        self.num_ctx = num_ctx
        self.max_retries = max_retries

    def load_prompt_template(self) -> str:
        """Load the prompt template for this agent from prompts/<role>.txt."""
        template_path = PROMPTS_DIR / f"{self.role}.txt"
        if not template_path.exists():
            raise FileNotFoundError(
                f"Prompt template not found: {template_path}\n"
                f"Create the file prompts/{self.role}.txt with your system prompt."
            )
        return template_path.read_text(encoding="utf-8").strip()

    def call_model(self, prompt: str) -> str:
        """Send prompt through the configured model adapter with
        resilience-aware failure classification, retry, and fallback
        (see orchestrator/resilience.py). Raises FatalModelError if all
        applicable retries/fallbacks are exhausted."""
        from orchestrator.config_loader import get_inference_defaults
        from orchestrator.resilience import call_with_resilience

        defaults = get_inference_defaults()
        temperature = getattr(self, "temperature", defaults.get("temperature", 0.7))
        num_ctx = getattr(self, "num_ctx", defaults.get("num_ctx", 4096))

        return call_with_resilience(
            model=self.model,
            prompt=prompt,
            temperature=temperature,
            num_ctx=num_ctx,
            role=self.role,
        )

    def run(self, **kwargs) -> str:
        """Override in subclasses. Returns the agent's output as a string."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement run()")
