"""
orchestrator/adapters.py

Model adapter interface and implementations.

All agent calls go through a ModelAdapter subclass. The active adapter is
selected by the 'provider' field in config/models.yaml. Adding a new provider
(e.g. OpenAI) requires only:
  1. Writing a new subclass of ModelAdapter
  2. Registering it in get_adapter()
  3. Setting provider: openai in models.yaml
  4. Providing the API key in .env

No changes to agent code are needed.
"""

import requests
from abc import ABC, abstractmethod

from orchestrator.config_loader import (
    get_ollama_base_url,
    get_keep_alive,
    get_ollama_timeout,
)
from orchestrator.resilience import (
    ModelConnectionError,
    ModelHTTPError,
    ModelTimeoutError,
)


# ── Base interface ────────────────────────────────────────────────────────────

class ModelAdapter(ABC):
    """
    Abstract base class for all model provider adapters.
    Every adapter must implement call().
    """

    @abstractmethod
    def call(self, model: str, prompt: str, temperature: float = 0.7,
             num_ctx: int = 4096, timeout: int | None = None) -> str:
        """
        Send a prompt to the model and return the response text.

        Args:
            model:       Provider-specific model identifier.
            prompt:      The full prompt string.
            temperature: Sampling temperature.
            num_ctx:     Context window size in tokens.
            timeout:     Optional per-call timeout override in seconds.

        Returns:
            The model's response as a plain string.
        """


# ── Ollama adapter (default) ──────────────────────────────────────────────────

class OllamaAdapter(ModelAdapter):
    """
    Calls the local Ollama server.
    No API key required. All inference is local and free.
    """

    def __init__(self):
        self.base_url = get_ollama_base_url()
        self.keep_alive = get_keep_alive()
        self.request_timeout = get_ollama_timeout()

    def call(self, model: str, prompt: str, temperature: float = 0.7,
             num_ctx: int = 4096, timeout: int | None = None) -> str:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": temperature,
                "num_ctx": num_ctx,
            },
        }
        effective_timeout = timeout if timeout is not None else self.request_timeout
        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=effective_timeout,
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except requests.exceptions.ConnectionError:
            raise ModelConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Is the Ollama app running? Run: open -a Ollama"
            )
        except requests.exceptions.Timeout:
            raise ModelTimeoutError(
                f"Ollama timed out after {effective_timeout}s on model '{model}'. "
                "Try a smaller model or check memory pressure."
            )
        except requests.exceptions.HTTPError as e:
            raise ModelHTTPError(f"Ollama HTTP error: {e} -- {resp.text[:300]}")


# ── Future adapter stubs ──────────────────────────────────────────────────────
# These are NOT implemented and will raise NotImplementedError if called.
# They exist as stubs to show how to add providers later.

class OpenAIAdapter(ModelAdapter):
    """
    Future: OpenAI API adapter.
    Requires: pip install openai
    Requires: OPENAI_API_KEY in .env
    To activate: set provider: openai in config/models.yaml
    """

    def call(self, model: str, prompt: str, temperature: float = 0.7,
             num_ctx: int = 4096, timeout: int | None = None) -> str:
        raise NotImplementedError(
            "OpenAI adapter is not yet implemented. "
            "Set provider: ollama in config/models.yaml to use local models. "
            "To implement later: pip install openai, add OPENAI_API_KEY to .env, "
            "then replace this raise with the OpenAI SDK call."
        )


class AnthropicAdapter(ModelAdapter):
    """
    Future: Anthropic Claude API adapter.
    Requires: pip install anthropic
    Requires: ANTHROPIC_API_KEY in .env
    To activate: set provider: anthropic in config/models.yaml
    """

    def call(self, model: str, prompt: str, temperature: float = 0.7,
             num_ctx: int = 4096, timeout: int | None = None) -> str:
        raise NotImplementedError(
            "Anthropic adapter is not yet implemented. "
            "Set provider: ollama in config/models.yaml to use local models."
        )


# ── Adapter factory ───────────────────────────────────────────────────────────

_adapter_cache: ModelAdapter | None = None


def get_adapter() -> ModelAdapter:
    """
    Return the active ModelAdapter based on config/models.yaml provider setting.
    Cached after first call — call reload_config() to reset.
    """
    global _adapter_cache
    if _adapter_cache is not None:
        return _adapter_cache

    from orchestrator.config_loader import get_provider
    provider = get_provider()

    if provider == "ollama":
        _adapter_cache = OllamaAdapter()
    elif provider == "openai":
        _adapter_cache = OpenAIAdapter()
    elif provider == "anthropic":
        _adapter_cache = AnthropicAdapter()
    else:
        raise ValueError(
            f"Unknown provider '{provider}' in config/models.yaml. "
            "Valid options: ollama, openai, anthropic"
        )

    return _adapter_cache
