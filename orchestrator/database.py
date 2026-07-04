"""
orchestrator/database.py

SQLite run history for the Local AI Orchestrator.
All database interaction goes through this module.

The database file lives at: runs/history.db
It is excluded from Git via .gitignore.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional


DB_PATH = Path("runs") / "history.db"


# ── Schema ────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     TEXT    NOT NULL,
    goal          TEXT    NOT NULL,
    refined_goal  TEXT,
    mode          TEXT    DEFAULT 'general',
    model_main    TEXT,
    model_fast    TEXT,
    final_score   INTEGER DEFAULT 0,
    passed        INTEGER DEFAULT 0,
    stop_reason   TEXT,
    iterations    INTEGER DEFAULT 0,
    scores_json   TEXT,
    run_dir       TEXT,
    final_output  TEXT
);

CREATE TABLE IF NOT EXISTS iterations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    iteration     INTEGER NOT NULL,
    critique      TEXT,
    revised_draft TEXT,
    verdict_json  TEXT,
    score         INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cloud_calls (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL,
    run_id          INTEGER REFERENCES runs(id) ON DELETE CASCADE,
    role            TEXT    NOT NULL,
    provider        TEXT    NOT NULL,
    model           TEXT    NOT NULL,
    input_tokens    INTEGER DEFAULT 0,
    output_tokens   INTEGER DEFAULT 0,
    cost_usd        REAL    DEFAULT 0,
    approved_by_user INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON runs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_iterations_run_id ON iterations(run_id);
CREATE INDEX IF NOT EXISTS idx_cloud_calls_timestamp ON cloud_calls(timestamp DESC);
"""


# ── Connection helper ─────────────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    """
    Open a connection to the SQLite database.
    Creates the database file and schema if they do not exist.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db():
    """Create tables if they do not exist. Safe to call multiple times."""
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


# ── Write operations ──────────────────────────────────────────────────────────

def save_run(
    goal: str,
    refined_goal: str,
    mode: str,
    model_main: str,
    model_fast: str,
    final_score: int,
    passed: bool,
    stop_reason: str,
    scores: list[int],
    run_dir: str,
    final_output: str,
    iterations_data: Optional[list[dict]] = None,
) -> int:
    """
    Save a completed pipeline run to the database.

    Args:
        iterations_data: list of dicts, each with keys:
            iteration, critique, revised_draft, verdict, score

    Returns:
        The database ID of the saved run.
    """
    init_db()
    iterations_data = iterations_data or []

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO runs (
            timestamp, goal, refined_goal, mode, model_main, model_fast,
            final_score, passed, stop_reason, iterations, scores_json,
            run_dir, final_output
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now().isoformat(timespec="seconds"),
            goal,
            refined_goal,
            mode,
            model_main,
            model_fast,
            int(final_score),
            1 if passed else 0,
            stop_reason,
            len(iterations_data),
            json.dumps(scores),
            run_dir,
            final_output,
        ),
    )

    run_id = int(cur.lastrowid)

    for item in iterations_data:
        verdict = item.get("verdict", item.get("verdict_json", {}))
        cur.execute(
            """
            INSERT INTO iterations (
                run_id, iteration, critique, revised_draft, verdict_json, score
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                int(item.get("iteration", 0)),
                item.get("critique", ""),
                item.get("revised_draft", ""),
                json.dumps(verdict),
                int(item.get("score", 0)),
            ),
        )

    conn.commit()
    conn.close()
    return run_id


# ── Read operations ───────────────────────────────────────────────────────────

def load_all_runs(limit: int = 20) -> list[dict]:
    """Return recent runs as summary dictionaries."""
    init_db()
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT *
        FROM runs
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()

    runs = []
    for row in rows:
        run = dict(row)
        run["passed"] = bool(run.get("passed"))
        run["scores_list"] = json.loads(run.get("scores_json") or "[]")
        runs.append(run)
    return runs


def load_run_by_id(run_id: int) -> Optional[dict]:
    """
    Return full details for one run, including all iteration data.
    Returns None if the run_id does not exist.
    """
    init_db()
    conn = get_connection()

    run_row = conn.execute(
        "SELECT * FROM runs WHERE id = ?", (run_id,)
    ).fetchone()

    if run_row is None:
        conn.close()
        return None

    run = dict(run_row)
    run["passed"] = bool(run.get("passed"))
    run["scores_list"] = json.loads(run.get("scores_json") or "[]")

    iteration_rows = conn.execute(
        """
        SELECT iteration, critique, revised_draft, verdict_json, score
        FROM iterations
        WHERE run_id = ?
        ORDER BY iteration ASC
        """,
        (run_id,),
    ).fetchall()

    run["iterations_detail"] = []
    for row in iteration_rows:
        item = dict(row)
        item["verdict"] = json.loads(item.get("verdict_json") or "{}")
        run["iterations_detail"].append(item)

    conn.close()
    return run


def load_recent_runs(n: int = 10) -> list[dict]:
    """Return the n most recent runs as summary dicts."""
    return load_all_runs(limit=n)


# ── Admin operations ──────────────────────────────────────────────────────────

def delete_run(run_id: int):
    """Delete one run and all its iterations."""
    init_db()
    conn = get_connection()
    conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
    conn.commit()
    conn.close()


def reset_database():
    """
    ⚠️ Deletes ALL run history. Use with caution.
    Drops and recreates all tables.
    """
    init_db()
    conn = get_connection()
    conn.executescript(
        """
        DROP TABLE IF EXISTS iterations;
        DROP TABLE IF EXISTS runs;
        """
    )
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def get_db_stats() -> dict:
    """Return basic stats about the database."""
    init_db()
    conn = get_connection()
    run_count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    avg_score = conn.execute(
        "SELECT AVG(final_score) FROM runs WHERE final_score > 0"
    ).fetchone()[0]
    pass_count = conn.execute(
        "SELECT COUNT(*) FROM runs WHERE passed = 1"
    ).fetchone()[0]
    conn.close()
    return {
        "total_runs": run_count,
        "passed_runs": pass_count,
        "average_score": round(avg_score or 0, 1),
    }


# ── Cloud fallback (Phase 7) ──────────────────────────────────────────────────

def save_cloud_call(
    run_id: Optional[int],
    role: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    approved_by_user: bool,
) -> int:
    """
    Record one cloud escalation attempt to the cloud_calls table -- the
    audit trail for anything that ever goes out to a cloud provider.
    `run_id` may be None if no database run record exists yet at the point
    the call is recorded.
    """
    init_db()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO cloud_calls (
            timestamp, run_id, role, provider, model,
            input_tokens, output_tokens, cost_usd, approved_by_user
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now().isoformat(timespec="seconds"),
            run_id,
            role,
            provider,
            model,
            int(input_tokens),
            int(output_tokens),
            float(cost_usd),
            1 if approved_by_user else 0,
        ),
    )
    call_id = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return call_id


def get_cloud_spend(period: str) -> float:
    """
    Sum cost_usd from cloud_calls for the current "daily" or "monthly"
    window, based on each row's ISO-format timestamp prefix. Returns 0.0
    if there are no matching rows (including when the table is empty).
    """
    if period not in ("daily", "monthly"):
        raise ValueError(f"Unknown period '{period}'. Valid options: daily, monthly")

    now = datetime.now()
    prefix = now.strftime("%Y-%m-%d") if period == "daily" else now.strftime("%Y-%m")

    init_db()
    conn = get_connection()
    row = conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0) FROM cloud_calls WHERE timestamp LIKE ?",
        (f"{prefix}%",),
    ).fetchone()
    conn.close()
    return float(row[0])
