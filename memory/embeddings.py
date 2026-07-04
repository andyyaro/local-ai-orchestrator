"""
memory/embeddings.py

Local embedding calls via Ollama's dedicated /api/embeddings endpoint
(Phase 9). Distinct from orchestrator/adapters.py's ModelAdapter.call(),
since embeddings return a vector, not text -- forcing this into that
interface would be the wrong abstraction.
"""

import requests

from orchestrator.config_loader import get_memory_config, get_ollama_base_url


class EmbeddingModelUnavailableError(Exception):
    """
    Raised when the configured embedding model can't be reached or isn't
    pulled locally. Never auto-pulled -- callers see the exact
    `ollama pull <model>` command to run themselves.
    """


def embed(text: str, model: str | None = None) -> list[float]:
    """
    Return an embedding vector for `text` using Ollama's /api/embeddings
    endpoint. Raises EmbeddingModelUnavailableError (never returns a
    silent empty vector) if Ollama isn't reachable or the embedding model
    isn't available -- this module never downloads a model for you.
    """
    embedding_model = model or get_memory_config().get("embedding_model", "nomic-embed-text")
    base_url = get_ollama_base_url()

    try:
        resp = requests.post(
            f"{base_url}/api/embeddings",
            json={"model": embedding_model, "prompt": text},
            timeout=60,
        )
    except requests.exceptions.ConnectionError as exc:
        raise EmbeddingModelUnavailableError(
            f"Cannot connect to Ollama at {base_url}. Is the Ollama app running? "
            "Run: open -a Ollama"
        ) from exc
    except requests.exceptions.Timeout as exc:
        raise EmbeddingModelUnavailableError(
            f"Ollama timed out generating an embedding with '{embedding_model}'."
        ) from exc

    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        raise EmbeddingModelUnavailableError(
            f"Ollama returned an error for embedding model '{embedding_model}' -- "
            f"is it pulled locally? Run: ollama pull {embedding_model} "
            f"(underlying error: {exc})"
        ) from exc

    embedding = resp.json().get("embedding")
    if not embedding:
        raise EmbeddingModelUnavailableError(
            f"Ollama returned no embedding vector for model '{embedding_model}'. "
            f"Confirm it is pulled: ollama pull {embedding_model}"
        )
    return embedding
