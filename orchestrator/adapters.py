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
    Future: Anthropic Claude API adapter, used by the optional Phase 7
    cloud escalation path (orchestrator/cloud_policy.py,
    orchestrator/cost_tracker.py). Requires: pip install anthropic,
    ANTHROPIC_API_KEY in .env, and cloud.enabled: true in
    config/models.yaml.

    Deliberately still unimplemented: the Phase 7 guide requires
    personally verifying the model ID and pricing in
    config/models.yaml's `cloud` section against Anthropic's current
    published documentation before wiring a real call here -- copying an
    unverified model ID or price from a research report risks a broken
    API call or an incorrect budget check in cost_tracker.py. That
    verification has not happened in this session, so this intentionally
    still raises NotImplementedError. Use MockCloudAdapter for all tests
    and any development work in the meantime.
    """

    def call(self, model: str, prompt: str, temperature: float = 0.7,
             num_ctx: int = 4096, timeout: int | None = None) -> str:
        raise NotImplementedError(
            "Anthropic adapter is not yet implemented: the model ID and "
            "pricing in config/models.yaml's cloud section have not been "
            "verified against Anthropic's current published documentation. "
            "Set provider: ollama in config/models.yaml to use local models."
        )


# ── Cloud escalation adapter factory (Phase 7) ────────────────────────────────

def get_cloud_adapter() -> ModelAdapter:
    """
    Return the adapter for the optional cloud escalation path, based on
    config/models.yaml's cloud.provider -- independent of the top-level
    `provider` field used by get_adapter(), which stays "ollama" for every
    local call even when cloud fallback is enabled. Only ever reached
    after orchestrator.cloud_policy.should_attempt_cloud() and human
    approval have already passed.
    """
    from orchestrator.config_loader import get_cloud_config
    provider = get_cloud_config().get("provider", "anthropic")
    if provider == "anthropic":
        return AnthropicAdapter()
    if provider == "openai":
        return OpenAIAdapter()
    raise ValueError(
        f"Unknown cloud provider '{provider}' in config/models.yaml's cloud "
        "section. Valid options: anthropic, openai"
    )


class MockCloudAdapter(ModelAdapter):
    """
    Test/development-only stand-in for a real cloud adapter. Returns a
    canned, deterministic response with no network call at all -- this is
    what every Phase 7 test uses, never AnthropicAdapter or OpenAIAdapter.
    Records every call it receives so tests can assert on what was sent.
    """

    def __init__(self, canned_response: str = "MOCK_CLOUD_RESPONSE"):
        self.canned_response = canned_response
        self.calls: list[dict] = []

    def call(self, model: str, prompt: str, temperature: float = 0.7,
             num_ctx: int = 4096, timeout: int | None = None) -> str:
        self.calls.append({
            "model": model,
            "prompt": prompt,
            "temperature": temperature,
            "num_ctx": num_ctx,
        })
        return self.canned_response


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
