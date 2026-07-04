"""
orchestrator/resilience.py

Failure classification and resilience-aware model calling.

A local Ollama call has exactly one client and one likely cause when it's
slow: the model is loading, the machine is under memory pressure, or the
model is genuinely slow at this prompt length. Retrying the identical call
after a fixed sleep doesn't address any of those causes, so this module
treats different failure classes differently:

- Connection error (plausibly transient, e.g. a dropped socket): retry once
  after a short fixed wait.
- Timeout (the model itself is too slow): don't retry the identical call —
  fall back once to a smaller, faster local model instead.
- HTTP error (a bad request, not a transient condition): fail fast. The
  cloud-backoff branch exists for Phase 7's future cloud adapter, which can
  return real 429/503s; Ollama's HTTP errors are all client-error-shaped
  today, so that branch is unreachable via Ollama and that's fine.
"""

import time

from orchestrator.config_loader import get_resilience_config

_LOCAL_RETRY_WAIT_SECONDS = 2.5

# Size-class heuristic for get_timeout_for_model(): substring-match the model
# name against markers for each class. Order matters — check largest first,
# since "14b" and "4b" style collisions don't occur in practice for the model
# names this repo actually uses, but checking large-to-small is the safer
# default if that ever changes.
_LARGE_MARKERS = ("13b", "14b", "34b", "70b")
_MEDIUM_MARKERS = ("7b", "8b", "12b")
_SMALL_MARKERS = ("1b", "3b")


class ModelCallError(Exception):
    """Base class for all model-call failures."""


class ModelConnectionError(ModelCallError):
    """The adapter could not connect to the model server at all."""


class ModelTimeoutError(ModelCallError):
    """The model call exceeded its timeout."""


class ModelHTTPError(ModelCallError):
    """The model server returned an HTTP error status."""


class FatalModelError(ModelCallError):
    """All applicable retries/fallbacks for this call were exhausted."""


def classify_failure(exc: Exception) -> str:
    """Return "connection", "timeout", "http", or "unknown" for exc."""
    if isinstance(exc, ModelConnectionError):
        return "connection"
    if isinstance(exc, ModelTimeoutError):
        return "timeout"
    if isinstance(exc, ModelHTTPError):
        return "http"
    return "unknown"


def get_timeout_for_model(model: str) -> int:
    """Map a model name to a size class and return its configured timeout,
    defaulting to resilience.timeouts.default for an unrecognized name."""
    timeouts = get_resilience_config().get("timeouts", {})
    model_lower = model.lower()

    if any(marker in model_lower for marker in _LARGE_MARKERS):
        size = "large"
    elif any(marker in model_lower for marker in _MEDIUM_MARKERS):
        size = "medium"
    elif any(marker in model_lower for marker in _SMALL_MARKERS):
        size = "small"
    else:
        size = "default"

    return int(timeouts.get(size, timeouts.get("default", 600)))


def call_with_resilience(model: str, prompt: str, temperature: float,
                         num_ctx: int, role: str, metrics=None) -> str:
    """
    Call `model` through the active adapter with failure-aware handling:
      - ModelConnectionError: retry once, after a short fixed wait.
      - ModelTimeoutError: do not retry the same model — fall back once to
        resilience.fallback_model instead.
      - ModelHTTPError: fail fast (not transient; a cloud-backoff branch is
        reserved for Phase 7's cloud adapter but unreachable via Ollama).
    Raises FatalModelError if all applicable retries/fallbacks fail.

    `metrics`, if given, is a Phase 5 RunMetrics instance (or any object with
    the same record_retry/record_fallback/record_timeout_event methods) used
    to report these events. Untyped here to avoid resilience.py importing
    orchestrator.metrics at all.
    """
    from orchestrator.adapters import get_adapter

    config = get_resilience_config()
    fallback_model = config.get("fallback_model")
    max_local_retries = int(config.get("max_local_retries", 1))
    adapter = get_adapter()
    timeout = get_timeout_for_model(model)

    try:
        return adapter.call(model=model, prompt=prompt, temperature=temperature,
                            num_ctx=num_ctx, timeout=timeout)
    except ModelConnectionError as exc:
        if metrics is not None:
            metrics.record_retry(role, model, "connection")
        if max_local_retries < 1:
            raise FatalModelError(
                f"{role}: connection to '{model}' failed "
                f"(max_local_retries is 0): {exc}"
            ) from exc
        time.sleep(_LOCAL_RETRY_WAIT_SECONDS)
        try:
            return adapter.call(model=model, prompt=prompt, temperature=temperature,
                                num_ctx=num_ctx, timeout=timeout)
        except ModelCallError as retry_exc:
            raise FatalModelError(
                f"{role}: retry after connection error to '{model}' "
                f"also failed: {retry_exc}"
            ) from retry_exc
    except ModelTimeoutError as exc:
        if metrics is not None:
            metrics.record_timeout_event(role, model)
        if not fallback_model or fallback_model == model:
            raise FatalModelError(
                f"{role}: '{model}' timed out and no distinct fallback "
                f"model is configured: {exc}"
            ) from exc
        if metrics is not None:
            metrics.record_fallback(role, model, fallback_model)
        fallback_timeout = get_timeout_for_model(fallback_model)
        try:
            return adapter.call(model=fallback_model, prompt=prompt,
                                temperature=temperature, num_ctx=num_ctx,
                                timeout=fallback_timeout)
        except ModelCallError as fallback_exc:
            raise FatalModelError(
                f"{role}: '{model}' timed out, and fallback model "
                f"'{fallback_model}' also failed: {fallback_exc}"
            ) from fallback_exc
    except ModelHTTPError as exc:
        raise FatalModelError(
            f"{role}: HTTP error calling '{model}': {exc}"
        ) from exc
