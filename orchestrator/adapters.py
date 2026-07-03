"""
orchestrator/adapters.py

Model adapter interface and local Ollama implementation.
All agent calls go through this adapter layer.
"""

import requests
from abc import ABC, abstractmethod

from orchestrator.config_loader import get_ollama_base_url, get_keep_alive


class ModelAdapter(ABC):
    """Abstract base class for model provider adapters."""

    @abstractmethod
    def call(self, model: str, prompt: str,
             temperature: float = 0.7, num_ctx: int = 4096) -> str:
        """Send a prompt to the model and return response text."""


class OllamaAdapter(ModelAdapter):
    """Calls the local Ollama server. No API key required."""

    def __init__(self):
        self.base_url = get_ollama_base_url()
        self.keep_alive = get_keep_alive()

    def call(self, model: str, prompt: str,
             temperature: float = 0.7, num_ctx: int = 4096) -> str:
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
        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=180,
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Is the Ollama app running? Run: open -a Ollama"
            )
        except requests.exceptions.Timeout:
            raise RuntimeError(
                f"Ollama timed out on model '{model}'. "
                "Try a smaller model or check memory pressure."
            )
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"Ollama HTTP error: {e} -- {resp.text[:300]}")


class UnsupportedAdapter(ModelAdapter):
    """Placeholder for future non-local providers."""

    def call(self, model: str, prompt: str,
             temperature: float = 0.7, num_ctx: int = 4096) -> str:
        raise NotImplementedError(
            "This provider is not implemented yet. "
            "Set provider: ollama in config/models.yaml to use local models."
        )


_adapter_cache: ModelAdapter | None = None


def get_adapter() -> ModelAdapter:
    """Return the active model adapter based on config/models.yaml."""
    global _adapter_cache
    if _adapter_cache is not None:
        return _adapter_cache

    from orchestrator.config_loader import get_provider
    provider = get_provider()

    if provider == "ollama":
        _adapter_cache = OllamaAdapter()
    elif provider in {"openai", "anthropic"}:
        _adapter_cache = UnsupportedAdapter()
    else:
        raise ValueError(
            f"Unknown provider '{provider}' in config/models.yaml. "
            "Valid options: ollama, openai, anthropic"
        )

    return _adapter_cache
