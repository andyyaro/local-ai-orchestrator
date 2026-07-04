import pytest

import orchestrator.resilience as resilience
from orchestrator.resilience import (
    FatalModelError,
    ModelConnectionError,
    ModelHTTPError,
    ModelTimeoutError,
    call_with_resilience,
    classify_failure,
    get_timeout_for_model,
)


class FakeAdapter:
    """Records every call and returns/raises the next scripted outcome."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def call(self, model, prompt, temperature, num_ctx, timeout=None):
        self.calls.append(model)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    monkeypatch.setattr(resilience.time, "sleep", lambda seconds: None)


def _patch_resilience_config(monkeypatch, **overrides):
    config = {
        "fallback_model": "llama3.2:3b",
        "max_local_retries": 1,
        "timeouts": {"default": 600, "small": 120, "medium": 300, "large": 600},
    }
    config.update(overrides)
    monkeypatch.setattr(resilience, "get_resilience_config", lambda: config)
    return config


def _patch_adapter(monkeypatch, fake_adapter):
    monkeypatch.setattr("orchestrator.adapters.get_adapter", lambda: fake_adapter)


# ── classify_failure ──────────────────────────────────────────────────────────

def test_classify_failure_connection():
    assert classify_failure(ModelConnectionError("x")) == "connection"


def test_classify_failure_timeout():
    assert classify_failure(ModelTimeoutError("x")) == "timeout"


def test_classify_failure_http():
    assert classify_failure(ModelHTTPError("x")) == "http"


def test_classify_failure_unknown_for_unrelated_exception():
    assert classify_failure(ValueError("x")) == "unknown"


# ── get_timeout_for_model ─────────────────────────────────────────────────────

def test_get_timeout_for_model_small(monkeypatch):
    _patch_resilience_config(monkeypatch)
    assert get_timeout_for_model("llama3.2:3b") == 120


def test_get_timeout_for_model_large(monkeypatch):
    _patch_resilience_config(monkeypatch)
    assert get_timeout_for_model("qwen2.5:14b") == 600


def test_get_timeout_for_model_medium(monkeypatch):
    _patch_resilience_config(monkeypatch)
    assert get_timeout_for_model("gemma3:12b") == 300


def test_get_timeout_for_model_defaults_for_unrecognized_name(monkeypatch):
    _patch_resilience_config(monkeypatch)
    assert get_timeout_for_model("mystery-model") == 600


# ── call_with_resilience ──────────────────────────────────────────────────────

def test_call_with_resilience_retries_once_on_connection_error(monkeypatch):
    _patch_resilience_config(monkeypatch)
    fake = FakeAdapter([ModelConnectionError("dropped"), "success text"])
    _patch_adapter(monkeypatch, fake)

    result = call_with_resilience(
        model="qwen2.5:14b", prompt="hi", temperature=0.7, num_ctx=4096, role="builder",
    )

    assert result == "success text"
    assert fake.calls == ["qwen2.5:14b", "qwen2.5:14b"]


def test_call_with_resilience_falls_back_once_on_timeout(monkeypatch):
    _patch_resilience_config(monkeypatch)
    fake = FakeAdapter([ModelTimeoutError("too slow"), "fallback text"])
    _patch_adapter(monkeypatch, fake)

    result = call_with_resilience(
        model="qwen2.5:14b", prompt="hi", temperature=0.7, num_ctx=4096, role="builder",
    )

    assert result == "fallback text"
    assert fake.calls == ["qwen2.5:14b", "llama3.2:3b"]


def test_call_with_resilience_raises_fatal_when_fallback_also_times_out(monkeypatch):
    _patch_resilience_config(monkeypatch)
    fake = FakeAdapter([ModelTimeoutError("too slow"), ModelTimeoutError("still slow")])
    _patch_adapter(monkeypatch, fake)

    with pytest.raises(FatalModelError):
        call_with_resilience(
            model="qwen2.5:14b", prompt="hi", temperature=0.7, num_ctx=4096, role="builder",
        )

    assert fake.calls == ["qwen2.5:14b", "llama3.2:3b"]


def test_call_with_resilience_raises_fatal_when_retry_after_connection_error_also_fails(monkeypatch):
    _patch_resilience_config(monkeypatch)
    fake = FakeAdapter([ModelConnectionError("dropped"), ModelConnectionError("dropped again")])
    _patch_adapter(monkeypatch, fake)

    with pytest.raises(FatalModelError):
        call_with_resilience(
            model="qwen2.5:14b", prompt="hi", temperature=0.7, num_ctx=4096, role="builder",
        )

    assert fake.calls == ["qwen2.5:14b", "qwen2.5:14b"]


def test_call_with_resilience_fails_fast_on_http_error(monkeypatch):
    _patch_resilience_config(monkeypatch)
    fake = FakeAdapter([ModelHTTPError("400 bad request")])
    _patch_adapter(monkeypatch, fake)

    with pytest.raises(FatalModelError):
        call_with_resilience(
            model="qwen2.5:14b", prompt="hi", temperature=0.7, num_ctx=4096, role="builder",
        )

    assert fake.calls == ["qwen2.5:14b"]


def test_call_with_resilience_succeeds_on_first_try(monkeypatch):
    _patch_resilience_config(monkeypatch)
    fake = FakeAdapter(["all good"])
    _patch_adapter(monkeypatch, fake)

    result = call_with_resilience(
        model="qwen2.5:14b", prompt="hi", temperature=0.7, num_ctx=4096, role="builder",
    )

    assert result == "all good"
    assert fake.calls == ["qwen2.5:14b"]
