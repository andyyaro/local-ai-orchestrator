"""
agents/base_agent.py

Base class for all pipeline agents. Provides shared model-call logic,
prompt template loading, and error handling. All agent classes inherit from
BaseAgent and override the run() method.
"""

import time
import sys
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
        """Send prompt through the configured model adapter with retry."""
        from orchestrator.adapters import get_adapter
        from orchestrator.config_loader import get_inference_defaults

        adapter = get_adapter()
        defaults = get_inference_defaults()
        temperature = getattr(self, "temperature", defaults.get("temperature", 0.7))
        num_ctx = getattr(self, "num_ctx", defaults.get("num_ctx", 4096))

        for attempt in range(1, self.max_retries + 2):
            try:
                text = adapter.call(
                    model=self.model,
                    prompt=prompt,
                    temperature=temperature,
                    num_ctx=num_ctx,
                )
                if not text:
                    raise ValueError("Adapter returned empty response.")
                return text
            except RuntimeError as e:
                if attempt <= self.max_retries:
                    print(f"  [WARN] {self.role} attempt {attempt} failed: {e}. Retrying...")
                    time.sleep(3)
                    continue
                self._fatal(str(e))
            except ValueError as e:
                if attempt <= self.max_retries:
                    print(f"  [WARN] {self.role} empty response, retrying...")
                    time.sleep(2)
                    continue
                self._fatal(str(e))

        self._fatal("All retry attempts exhausted.")

    def _fatal(self, message: str):
        """Print an error message and exit."""
        print(f"\n[ERROR] Agent '{self.role}' failed: {message}")
        sys.exit(1)

    def run(self, **kwargs) -> str:
        """Override in subclasses. Returns the agent's output as a string."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement run()")
