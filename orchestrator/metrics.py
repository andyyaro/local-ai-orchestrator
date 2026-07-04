"""
orchestrator/metrics.py

Aggregates one pipeline run's instrumentation into a single summary dict so
routing (Phase 3), resilience (Phase 4), and future model-profile changes can
be verified with real numbers instead of assumed.

RunMetrics is a passive collector: other modules call into it during a run,
and it is finalized once at the end. It must not import from resilience.py,
adapters.py, or run.py, so it can be constructed fresh in tests without any
import-order concerns.
"""

from collections import defaultdict


class RunMetrics:
    """Collects per-run instrumentation for one pipeline run."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self._per_agent: dict[str, dict] = defaultdict(
            lambda: {"model": None, "calls": 0, "elapsed_ms": 0}
        )
        self._calls_by_model: dict[str, int] = defaultdict(int)
        self.path: str | None = None
        self.retries = 0
        self.fallbacks = 0
        self.timeout_events = 0
        self._validator_failures: dict[str, int] = defaultdict(int)
        self._hard_fails: dict[str, int] = defaultdict(int)

    def record_agent_call(self, role: str, model: str, elapsed_ms: int):
        entry = self._per_agent[role]
        entry["model"] = model
        entry["calls"] += 1
        entry["elapsed_ms"] += elapsed_ms
        self._calls_by_model[model] += 1

    def record_path(self, path: str):
        self.path = path

    def record_retry(self, role: str, model: str, failure_type: str):
        self.retries += 1

    def record_fallback(self, role: str, from_model: str, to_model: str):
        self.fallbacks += 1

    def record_timeout_event(self, role: str, model: str):
        self.timeout_events += 1

    def record_validator_failure(self, rule: str):
        self._validator_failures[rule] += 1

    def record_hard_fail(self, reason: str):
        self._hard_fails[reason] += 1

    def finalize(self, total_elapsed_ms: int) -> dict:
        """Return the aggregated summary for this run."""
        return {
            "total_elapsed_ms": total_elapsed_ms,
            "per_agent": {role: dict(data) for role, data in self._per_agent.items()},
            "calls_by_model": dict(self._calls_by_model),
            "path": self.path,
            "retries": self.retries,
            "fallbacks": self.fallbacks,
            "timeout_events": self.timeout_events,
            "validator_failures": dict(self._validator_failures),
            "hard_fails": dict(self._hard_fails),
        }
