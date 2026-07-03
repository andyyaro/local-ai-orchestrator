"""Small Ollama HTTP client for local model calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


class OllamaError(RuntimeError):
    """Raised when the local Ollama server is unavailable or returns an error."""


@dataclass(frozen=True)
class OllamaClient:
    """Minimal client for Ollama's local generate endpoint."""

    base_url: str = "http://localhost:11434"
    timeout_seconds: int = 180

    def health_check(self) -> bool:
        """Return True if the local Ollama server is reachable."""
        try:
            response = requests.get(self.base_url, timeout=5)
        except requests.RequestException:
            return False
        return response.ok and "Ollama is running" in response.text

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        system: str | None = None,
        keep_alive: str | None = "5m",
        options: dict[str, Any] | None = None,
    ) -> str:
        """Generate a non-streaming response from a local Ollama model."""
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }

        if system:
            payload["system"] = system
        if keep_alive:
            payload["keep_alive"] = keep_alive
        if options:
            payload["options"] = options

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise OllamaError(
                "Could not connect to Ollama. Start Ollama and verify it with: "
                "curl http://localhost:11434"
            ) from exc

        if not response.ok:
            raise OllamaError(f"Ollama request failed with HTTP {response.status_code}: {response.text}")

        data = response.json()
        generated = data.get("response")
        if not isinstance(generated, str):
            raise OllamaError(f"Ollama response did not contain a text response: {data}")

        return generated.strip()
