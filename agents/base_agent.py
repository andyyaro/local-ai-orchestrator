"""
agents/base_agent.py

Base class for all pipeline agents. Provides shared Ollama call logic,
prompt template loading, and error handling. All agent classes inherit from
BaseAgent and override the `run()` method.
"""

import requests
import json
import time
import sys
from pathlib import Path


OLLAMA_URL = "http://localhost:11434/api/generate"
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class BaseAgent:
    """
    Shared foundation for all pipeline agents.

    Subclasses must set self.role and self.model, then implement run().
    """

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
        """
        Send a prompt to Ollama and return the response text.
        Retries up to self.max_retries times on transient errors.
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.num_ctx,
            },
        }

        for attempt in range(1, self.max_retries + 2):
            try:
                response = requests.post(
                    OLLAMA_URL, json=payload, timeout=180
                )
                response.raise_for_status()
                data = response.json()
                text = data.get("response", "").strip()
                if not text:
                    raise ValueError("Ollama returned an empty response.")
                return text

            except requests.exceptions.ConnectionError:
                self._fatal(
                    "Cannot connect to Ollama at http://localhost:11434\n"
                    "Start Ollama: open -a Ollama"
                )

            except requests.exceptions.Timeout:
                if attempt <= self.max_retries:
                    print(f"  [WARN] Timeout on attempt {attempt}, retrying...")
                    time.sleep(3)
                    continue
                self._fatal(
                    f"Request timed out after {self.max_retries + 1} attempts.\n"
                    "Try a smaller model or check memory pressure."
                )

            except (requests.exceptions.HTTPError, ValueError) as e:
                if attempt <= self.max_retries:
                    print(f"  [WARN] Error on attempt {attempt}: {e}. Retrying...")
                    time.sleep(3)
                    continue
                self._fatal(str(e))

        self._fatal("All retry attempts failed.")

    def _fatal(self, message: str):
        """Print an error message and exit."""
        print(f"\n[ERROR] Agent '{self.role}' failed: {message}")
        sys.exit(1)

    def run(self, **kwargs) -> str:
        """Override in subclasses. Returns the agent's output as a string."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement run()")
