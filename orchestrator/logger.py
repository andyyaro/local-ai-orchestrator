"""
orchestrator/logger.py

Structured logging for the Local AI Orchestrator.
Writes JSON-structured log entries to logs/pipeline.log.
Each entry includes: timestamp, run_id, agent, model, event, and details.

Usage:
    from orchestrator.logger import get_logger
    log = get_logger("my_run_id")
    log.agent_start("builder", "qwen2.5:14b")
    log.agent_end("builder", chars=1200)
    log.score(iteration=1, score=74, passed=False)
    log.stop(reason="max_loops")
    log.error("builder", "Connection refused")
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path


LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

LOG_FILE = LOGS_DIR / "pipeline.log"


def _setup_file_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)

    # File handler: JSON lines format
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(message)s"))

    # Console handler: human-readable (errors only)
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.WARNING)
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


class PipelineLogger:
    """
    Thin wrapper around Python logging that writes structured JSON entries
    to logs/pipeline.log. One instance per pipeline run.
    """

    def __init__(self, run_id: str):
        self.run_id = run_id
        self._logger = _setup_file_logger("orchestrator")

    def _write(self, level: str, event: str, **kwargs):
        entry = {
            "ts": datetime.now().isoformat(timespec="milliseconds"),
            "run_id": self.run_id,
            "event": event,
            **kwargs,
        }
        line = json.dumps(entry, ensure_ascii=False)
        if level == "ERROR":
            self._logger.error(line)
        elif level == "WARNING":
            self._logger.warning(line)
        else:
            self._logger.info(line)

    def run_start(self, goal: str, model_main: str, model_fast: str,
                  max_loops: int, threshold: int):
        self._write("INFO", "run_start", goal=goal[:200],
                    model_main=model_main, model_fast=model_fast,
                    max_loops=max_loops, threshold=threshold)

    def agent_start(self, agent: str, model: str, iteration: int = 0):
        self._write("INFO", "agent_start", agent=agent,
                    model=model, iteration=iteration)

    def agent_end(self, agent: str, chars: int, elapsed_ms: int = 0):
        self._write("INFO", "agent_end", agent=agent,
                    output_chars=chars, elapsed_ms=elapsed_ms)

    def score(self, iteration: int, score: int, passed: bool,
              category_scores: dict | None = None, hard_fails: list | None = None):
        self._write("INFO", "score", iteration=iteration, score=score,
                    passed=passed, category_scores=category_scores or {},
                    hard_fails=hard_fails or [])

    def code_verification(self, iteration: int, success: bool,
                          hard_fail: bool, summary: str):
        self._write("INFO", "code_verification", iteration=iteration,
                    success=success, hard_fail=hard_fail,
                    summary=summary[:300])

    def stop(self, reason: str, final_score: int, iterations: int):
        self._write("INFO", "run_stop", stop_reason=reason,
                    final_score=final_score, iterations_run=iterations)

    def error(self, agent: str, message: str, attempt: int = 1):
        self._write("ERROR", "agent_error", agent=agent,
                    message=message[:500], attempt=attempt)

    def warning(self, message: str, context: str = ""):
        self._write("WARNING", "warning", message=message[:300], context=context)

    def json_parse_failure(self, agent: str, raw_output: str, attempt: int):
        self._write("WARNING", "json_parse_failure", agent=agent,
                    attempt=attempt, raw_preview=raw_output[:300])


def get_logger(run_id: str) -> PipelineLogger:
    return PipelineLogger(run_id)
