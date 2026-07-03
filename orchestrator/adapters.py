import requests
from abc import ABC, abstractmethod

from orchestrator.config_loader import get_ollama_base_url, get_keep_alive, get_ollama_timeout


class ModelAdapter(ABC):
    @abstractmethod
    def call(self, model: str, prompt: str,
             temperature: float = 0.7, num_ctx: int = 4096) -> str:
        pass


class OllamaAdapter(ModelAdapter):
    def __init__(self):
        self.base_url = get_ollama_base_url()
        self.keep_alive = get_keep_alive()
        self.request_timeout = get_ollama_timeout()

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
                timeout=self.request_timeout,
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                f"Cannot connect to Ollama at {self.base_url}. Start Ollama and retry."
            )
        except requests.exceptions.Timeout:
            raise RuntimeError(
                f"Ollama timed out after {self.request_timeout}s on model '{model}'."
            )
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"Ollama HTTP error: {e} -- {resp.text[:300]}")


class UnsupportedAdapter(ModelAdapter):
    def call(self, model: str, prompt: str,
             temperature: float = 0.7, num_ctx: int = 4096) -> str:
        raise NotImplementedError("Selected provider is not implemented in the local MVP.")


_adapter_cache: ModelAdapter | None = None


def get_adapter() -> ModelAdapter:
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
        raise ValueError(f"Unknown provider '{provider}' in config/models.yaml.")

    return _adapter_cache
