import orchestrator.resilience as resilience
from agents.base_agent import BaseAgent


class _ConcreteAgent(BaseAgent):
    """Minimal concrete subclass so call_model() can be exercised directly."""

    def run(self, **kwargs) -> str:
        return self.call_model("hi")


def test_call_model_passes_agent_metrics_into_call_with_resilience(monkeypatch):
    captured = {}

    def fake_call_with_resilience(model, prompt, temperature, num_ctx, role, metrics=None):
        captured["model"] = model
        captured["role"] = role
        captured["metrics"] = metrics
        return "ok"

    monkeypatch.setattr(resilience, "call_with_resilience", fake_call_with_resilience)

    sentinel_metrics = object()
    agent = _ConcreteAgent(model="qwen2.5:14b", role="builder", metrics=sentinel_metrics)
    result = agent.run()

    assert result == "ok"
    assert captured["model"] == "qwen2.5:14b"
    assert captured["role"] == "builder"
    assert captured["metrics"] is sentinel_metrics


def test_call_model_defaults_metrics_to_none_when_not_supplied(monkeypatch):
    captured = {}

    def fake_call_with_resilience(model, prompt, temperature, num_ctx, role, metrics=None):
        captured["metrics"] = metrics
        return "ok"

    monkeypatch.setattr(resilience, "call_with_resilience", fake_call_with_resilience)

    agent = _ConcreteAgent(model="llama3.2:3b", role="critic")
    agent.run()

    assert captured["metrics"] is None
