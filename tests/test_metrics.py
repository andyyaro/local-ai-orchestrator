from orchestrator.metrics import RunMetrics


# ── record_agent_call / finalize per-agent breakdown ─────────────────────────

def test_record_agent_call_aggregates_multiple_calls_to_same_role():
    metrics = RunMetrics("run-1")
    metrics.record_agent_call("critic", "gemma3:12b", 100)
    metrics.record_agent_call("critic", "gemma3:12b", 250)

    summary = metrics.finalize(total_elapsed_ms=1000)

    assert summary["per_agent"]["critic"] == {
        "model": "gemma3:12b",
        "calls": 2,
        "elapsed_ms": 350,
    }
    assert summary["total_elapsed_ms"] == 1000


def test_finalize_includes_multiple_distinct_roles():
    metrics = RunMetrics("run-1")
    metrics.record_agent_call("builder", "qwen2.5:14b", 500)
    metrics.record_agent_call("judge", "phi4:14b", 300)

    summary = metrics.finalize(total_elapsed_ms=900)

    assert summary["per_agent"]["builder"]["calls"] == 1
    assert summary["per_agent"]["judge"]["calls"] == 1


# ── calls_by_model grouping ───────────────────────────────────────────────────

def test_finalize_groups_calls_by_model_across_roles():
    metrics = RunMetrics("run-1")
    metrics.record_agent_call("builder", "qwen2.5:14b", 100)
    metrics.record_agent_call("fixer", "qwen2.5:14b", 100)
    metrics.record_agent_call("judge", "qwen2.5:14b", 100)
    metrics.record_agent_call("supervisor", "llama3.2:3b", 50)

    summary = metrics.finalize(total_elapsed_ms=350)

    assert summary["calls_by_model"] == {
        "qwen2.5:14b": 3,
        "llama3.2:3b": 1,
    }


# ── record_path ────────────────────────────────────────────────────────────────

def test_record_path_shows_up_in_finalize():
    metrics = RunMetrics("run-1")
    metrics.record_path("fast")

    summary = metrics.finalize(total_elapsed_ms=0)

    assert summary["path"] == "fast"


# ── record_retry / record_fallback / record_timeout_event ───────────────────

def test_record_retry_fallback_and_timeout_event_counts():
    metrics = RunMetrics("run-1")
    metrics.record_retry("builder", "qwen2.5:14b", "connection")
    metrics.record_retry("builder", "qwen2.5:14b", "connection")
    metrics.record_fallback("builder", "qwen2.5:14b", "llama3.2:3b")
    metrics.record_timeout_event("builder", "qwen2.5:14b")

    summary = metrics.finalize(total_elapsed_ms=0)

    assert summary["retries"] == 2
    assert summary["fallbacks"] == 1
    assert summary["timeout_events"] == 1


# ── record_validator_failure / record_hard_fail ──────────────────────────────

def test_record_validator_failure_counts_by_rule():
    metrics = RunMetrics("run-1")
    metrics.record_validator_failure("word_limit")
    metrics.record_validator_failure("word_limit")
    metrics.record_validator_failure("code_block_presence")

    summary = metrics.finalize(total_elapsed_ms=0)

    assert summary["validator_failures"] == {
        "word_limit": 2,
        "code_block_presence": 1,
    }


def test_record_hard_fail_counts_by_reason():
    metrics = RunMetrics("run-1")
    metrics.record_hard_fail("broken_code")
    metrics.record_hard_fail("constraint_violation")
    metrics.record_hard_fail("constraint_violation")

    summary = metrics.finalize(total_elapsed_ms=0)

    assert summary["hard_fails"] == {
        "broken_code": 1,
        "constraint_violation": 2,
    }


# ── zero-events case ─────────────────────────────────────────────────────────

def test_finalize_with_no_events_returns_clean_zeroed_summary():
    metrics = RunMetrics("run-1")

    summary = metrics.finalize(total_elapsed_ms=1234)

    assert summary == {
        "total_elapsed_ms": 1234,
        "per_agent": {},
        "calls_by_model": {},
        "path": None,
        "retries": 0,
        "fallbacks": 0,
        "timeout_events": 0,
        "validator_failures": {},
        "hard_fails": {},
    }
