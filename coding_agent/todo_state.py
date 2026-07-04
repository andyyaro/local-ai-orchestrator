"""
coding_agent/todo_state.py

Simple, persisted (JSON file per session) task tracking for Phase 11's
coding-agent loop -- gives both the loop and a human reviewing afterward
visibility into what the agent thought it was doing at each point, not
just what it actually changed.
"""

import json
from pathlib import Path

_VALID_STATUSES = {"pending", "in_progress", "done"}


class TodoState:
    """A simple ordered list of steps with a status, optionally persisted
    to a JSON file after every mutation."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else None
        self.steps: list[dict] = []

    def add_step(self, description: str, status: str = "pending") -> int:
        if status not in _VALID_STATUSES:
            raise ValueError(f"Invalid status '{status}'. Valid: {sorted(_VALID_STATUSES)}")
        self.steps.append({"description": description, "status": status})
        self._save()
        return len(self.steps) - 1

    def update_status(self, index: int, status: str) -> None:
        if status not in _VALID_STATUSES:
            raise ValueError(f"Invalid status '{status}'. Valid: {sorted(_VALID_STATUSES)}")
        self.steps[index]["status"] = status
        self._save()

    def _save(self) -> None:
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.steps, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "TodoState":
        state = cls(path=path)
        path = Path(path)
        if path.exists():
            state.steps = json.loads(path.read_text(encoding="utf-8"))
        return state
