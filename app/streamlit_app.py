"""
app/streamlit_app.py

Streamlit dashboard for the Local AI Orchestrator.
Calls run.py's run_pipeline() directly (Phase 8) instead of maintaining a
second, independent copy of the pipeline -- every phase wired into
run_pipeline() (validators, routing, resilience, metrics, memory
discipline, cloud gating) applies here automatically.

Run with:
    streamlit run app/streamlit_app.py
"""

import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue

import streamlit as st

# Make sure the project root is on sys.path so agents/ can be imported.
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from run import run_pipeline
from orchestrator.cloud_policy import is_cloud_enabled
from orchestrator.config_loader import get_active_profile
from orchestrator.database import get_db_stats, load_all_runs, load_run_by_id

RUNS_DIR = ROOT / "runs"
RUNS_DIR.mkdir(exist_ok=True)

DEFAULT_MAX_LOOPS = 3
DEFAULT_THRESHOLD = 70
DEFAULT_MIN_IMPROVEMENT = 5


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_run_dir() -> Path:
    """Create a Streamlit-specific run folder under runs/."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RUNS_DIR / f"ui_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def normalize_override(value: str) -> str | None:
    """Convert the UI's config-driven option into the None override used by code."""
    return None if value == "config-driven" else value


def render_score_status(score: int, threshold: int) -> str:
    if score >= threshold:
        return "Passed"
    return "Below threshold"


def render_status_pill(label: str, tone: str = "neutral"):
    st.markdown(
        f'<span class="status-pill status-{tone}">{label}</span>',
        unsafe_allow_html=True,
    )


# ── Pipeline runner ──────────────────────────────────────────────────────────

def run_pipeline_thread(
    goal: str,
    model_main: str | None,
    model_fast: str | None,
    max_loops: int,
    threshold: int,
    min_improvement: int,
    run_dir: Path,
    event_queue: Queue,
    path_override: str | None = None,
    allow_cloud: bool = False,
):
    """
    Runs run.py's real run_pipeline() in a background thread, forwarding
    its on_step events straight to event_queue so the UI updates exactly
    as before -- this replaces the previous separate, duplicated pipeline
    implementation (Phase 8). Every phase wired into run_pipeline() (Phase 2
    validators, Phase 3 routing, Phase 4 resilience, Phase 5 metrics, Phase 6
    memory discipline, Phase 7 cloud gating) now applies here too, since
    this is the same function the CLI calls.
    """
    try:
        summary, final_output = run_pipeline(
            goal=goal,
            model_main=model_main,
            model_fast=model_fast,
            max_loops=max_loops,
            threshold=threshold,
            min_improvement=min_improvement,
            run_dir=run_dir,
            path_override=path_override,
            allow_cloud=allow_cloud,
            on_step=lambda event: event_queue.put(event),
        )
        event_queue.put({
            "type": "final",
            "output": final_output,
            "summary": summary,
            "run_dir": str(run_dir),
        })
    except Exception as exc:  # pragma: no cover - visible in UI during manual runs
        event_queue.put({"type": "error", "message": str(exc)})


# ── Page config and styling ──────────────────────────────────────────────────

st.set_page_config(
    page_title="Local AI Orchestrator",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed",
)


st.markdown(
    """
<style>
:root {
    --bg: #fbfaf7;
    --surface: #ffffff;
    --surface-soft: #f4efe6;
    --surface-muted: #ede5d7;
    --text: #111111;
    --text-muted: #5f5a52;
    --border: #ded6c8;
    --green: #1f7a4d;
    --green-dark: #145c39;
    --green-soft: #e6f2eb;
}

html, body, [class*="css"] {
    font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.stApp {
    background: var(--bg);
    color: var(--text);
}

[data-testid="stSidebar"] {
    background: var(--surface-soft);
    border-right: 1px solid var(--border);
}

[data-testid="stSidebar"] * {
    color: var(--text);
}

[data-testid="stHeader"] {
    background: rgba(251, 250, 247, 0.82);
    backdrop-filter: blur(16px);
}

#MainMenu, footer, [data-testid="stDecoration"], [data-testid="stToolbar"] {
    visibility: hidden;
    height: 0;
}

.block-container {
    max-width: 880px;
    padding-top: 1.4rem;
    padding-bottom: 3rem;
}

h1, h2, h3 {
    color: var(--text);
    letter-spacing: -0.035em;
}

h1 {
    font-size: 2rem !important;
    line-height: 1.1 !important;
    margin-bottom: 0.15rem !important;
}

h2 {
    font-size: 1rem !important;
    margin-top: 0.7rem !important;
    letter-spacing: -0.02em;
}

h3 {
    font-size: 1rem !important;
    letter-spacing: 0 !important;
}

p, li, label, .stMarkdown, .stCaption {
    color: var(--text);
}

.small-muted {
    color: var(--text-muted);
    font-size: 0.94rem;
    line-height: 1.6;
}

.hero {
    background: transparent;
    border: 0;
    border-radius: 0;
    padding: 0;
    margin-bottom: 1rem;
}

.hero-kicker {
    display: none;
}

.hero-subtitle {
    max-width: 520px;
    color: var(--text-muted);
    font-size: 0.9rem;
    line-height: 1.35;
    margin-top: 0.25rem;
}

.card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 22px;
    padding: 1.2rem 1.25rem;
    margin-bottom: 1rem;
}

.card-soft {
    background: var(--surface-soft);
    border: 1px solid var(--border);
    border-radius: 22px;
    padding: 1.2rem 1.25rem;
    margin-bottom: 1rem;
}

.metric-card {
    display: none;
}

.metric-label {
    color: var(--text-muted);
    font-size: 0.76rem;
    font-weight: 750;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

.metric-value {
    color: var(--text);
    font-size: 1.8rem;
    font-weight: 800;
    margin-top: 0.35rem;
    letter-spacing: -0.045em;
}

.status-pill {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    padding: 0.32rem 0.72rem;
    font-size: 0.78rem;
    font-weight: 750;
    border: 1px solid var(--border);
    margin-right: 0.35rem;
}

.status-green {
    background: var(--green-soft);
    color: var(--green-dark);
    border-color: #b8d9c7;
}

.status-neutral {
    background: var(--surface-soft);
    color: var(--text-muted);
}

.status-dark {
    background: var(--text);
    color: white;
    border-color: var(--text);
}

hr {
    border-color: var(--border) !important;
}

div.stButton > button:first-child {
    background: var(--green) !important;
    color: #ffffff !important;
    border: 1px solid var(--green) !important;
    border-radius: 999px !important;
    padding: 0.68rem 1.35rem !important;
    font-weight: 800 !important;
}

div.stButton > button:first-child:hover {
    background: var(--green-dark) !important;
    color: #ffffff !important;
    border-color: var(--green-dark) !important;
}

.stDownloadButton button {
    background: var(--text) !important;
    color: white !important;
    border-radius: 999px !important;
    border: 1px solid var(--text) !important;
}

[data-testid="stTextArea"] textarea,
[data-testid="stSelectbox"] div,
[data-testid="stNumberInput"] input {
    background: var(--surface) !important;
    border-color: var(--border) !important;
    border-radius: 18px !important;
    color: var(--text) !important;
}

[data-testid="stMetric"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 1rem;
}

[data-testid="stMetricLabel"] {
    color: var(--text-muted);
}

[data-testid="stMetricValue"] {
    color: var(--text);
}

.stAlert {
    border-radius: 18px;
}

[data-testid="stStatusWidget"] {
    color: var(--green);
}

div[data-testid="stExpander"] {
    border: 1px solid var(--border);
    border-radius: 18px;
    background: var(--surface);
}

[data-testid="stDataFrame"] {
    border: 1px solid var(--border);
    border-radius: 18px;
    overflow: hidden;
}

code {
    color: var(--green-dark);
}
</style>
""",
    unsafe_allow_html=True,
)


# ── Sidebar — configuration ──────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## Controls")
    st.caption(f"`{get_active_profile()}` profile")

    # Mode is detected by the Supervisor from the goal text (see run.py) --
    # there is no mode override here, matching the CLI, which has never
    # exposed one either. Path (Phase 3 routing) IS overridable on the CLI
    # via --path, so it gets a real UI equivalent here instead.
    path_choice = st.selectbox(
        "Path",
        options=["auto", "fast", "normal", "deep"],
        index=0,
        help="'auto' classifies the goal automatically, same as the CLI's default.",
    )

    with st.expander("Run settings", expanded=False):
        max_loops = st.slider(
            "Max loops",
            min_value=1,
            max_value=6,
            value=DEFAULT_MAX_LOOPS,
            step=1,
        )
        threshold = st.slider(
            "Pass threshold",
            min_value=50,
            max_value=95,
            value=DEFAULT_THRESHOLD,
            step=5,
        )
        min_improvement = st.slider(
            "Minimum improvement",
            min_value=0,
            max_value=15,
            value=DEFAULT_MIN_IMPROVEMENT,
            step=1,
        )

    with st.expander("Model overrides", expanded=False):
        # Options mirror run.py's _role_model(): "Main model" covers
        # builder/fixer/judge/synthesizer, "Fast model" covers
        # supervisor/planner/critic -- there is no separate judge override,
        # matching the CLI's actual two-override capability exactly.
        # Kept in sync with config/models.yaml's actual profile contents
        # (Phase 6) -- gemma3:12b and phi4:14b no longer appear in any
        # profile, so they were removed from these lists.
        model_main_choice = st.selectbox(
            "Main model",
            options=[
                "config-driven",
                "qwen2.5:14b",
                "qwen2.5-coder:14b",
                "llama3.1:8b",
                "llama3.2:3b",
            ],
            index=0,
        )

        model_fast_choice = st.selectbox(
            "Fast model",
            options=[
                "config-driven",
                "llama3.2:3b",
                "llama3.1:8b",
            ],
            index=0,
        )

    if is_cloud_enabled():
        render_status_pill("Cloud enabled", "dark")
    else:
        render_status_pill("Local only", "green")

    with st.expander("Coding safety", expanded=False):
        st.caption(
            "If the Supervisor detects a coding task, generated Python is "
            "executed locally with a timeout and a safety blocklist. "
            "Review code before reusing it."
        )


# ── Main area ────────────────────────────────────────────────────────────────

st.markdown(
    """
<div class="hero">
    <h1>Local AI Orchestrator</h1>
    <div class="hero-subtitle">Private multi-agent runs on your Mac.</div>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown("## Task")

goal = st.text_area(
    "Goal",
    placeholder="What should the pipeline improve?",
    height=135,
    label_visibility="collapsed",
)

run_btn = st.button("Run pipeline", type="primary", width="stretch")

st.markdown("---")


# ── Run and display events ───────────────────────────────────────────────────

if run_btn:
    if not goal.strip():
        st.warning("Enter a goal before starting the pipeline.")
        st.stop()

    model_main = normalize_override(model_main_choice)
    model_fast = normalize_override(model_fast_choice)
    path_override = None if path_choice == "auto" else path_choice

    run_dir = make_run_dir()
    event_queue: Queue = Queue()

    st.markdown("## Progress")
    output_placeholder = st.container()
    score_placeholder = st.empty()
    final_placeholder = st.empty()
    summary_placeholder = st.empty()

    thread = threading.Thread(
        target=run_pipeline_thread,
        kwargs={
            "goal": goal.strip(),
            "model_main": model_main,
            "model_fast": model_fast,
            "max_loops": max_loops,
            "threshold": threshold,
            "min_improvement": min_improvement,
            "run_dir": run_dir,
            "event_queue": event_queue,
            "path_override": path_override,
        },
        daemon=True,
    )
    thread.start()

    agent_expanders = {}

    while thread.is_alive() or not event_queue.empty():
        try:
            event = event_queue.get(timeout=0.2)
        except Empty:
            time.sleep(0.2)
            continue

        etype = event.get("type")

        if etype == "step":
            agent = event["agent"]
            status = event["status"]
            output = event.get("output", "")
            with output_placeholder:
                if status == "running":
                    agent_expanders[agent] = st.status(
                        f"{agent}",
                        expanded=False,
                    )
                    agent_expanders[agent].write("Running")
                elif status == "done" and agent in agent_expanders:
                    agent_expanders[agent].update(
                        label=f"{agent}",
                        state="complete",
                        expanded=False,
                    )
                    with agent_expanders[agent]:
                        st.markdown(output)

        elif etype == "loop_start":
            with output_placeholder:
                st.markdown(
                    f"""
<div class="card-soft">
    <strong>Loop {event['iteration']} of {event['max_loops']}</strong>
</div>
""",
                    unsafe_allow_html=True,
                )

        elif etype == "loop_result":
            scores_so_far = event["scores"]
            with score_placeholder.container():
                st.markdown("## Score progression")
                score_cols = st.columns([1, 1, 3])
                with score_cols[0]:
                    st.metric("Current score", f"{scores_so_far[-1]}/100")
                with score_cols[1]:
                    st.metric("Status", render_score_status(scores_so_far[-1], threshold))
                with score_cols[2]:
                    if len(scores_so_far) > 1:
                        st.line_chart(
                            {"Score": scores_so_far},
                            width="stretch",
                            height=180,
                        )
                    else:
                        st.progress(scores_so_far[-1] / 100)

        elif etype == "final":
            output = event["output"]
            summary = event["summary"]

            with final_placeholder.container():
                st.markdown("---")
                st.markdown("## Final output")
                st.markdown(output)
                st.download_button(
                    label="Download final output",
                    data=output,
                    file_name="final_output.txt",
                    mime="text/plain",
                )

            with summary_placeholder.container():
                st.markdown("---")
                st.markdown("## Run summary")
                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.metric("Final score", f"{summary['final_score']}/100")
                col_b.metric("Result", "Passed" if summary["passed"] else "Failed")
                col_c.metric("Loops", summary["iterations_run"])
                col_d.metric("Mode", summary["mode"])

                st.caption(f"Stop reason: {summary['stop_reason']}")
                st.caption(f"Run saved to: {event['run_dir']}")
                st.caption(f"Database ID: {summary['db_run_id']}")
                if summary.get("path"):
                    st.caption(f"Path selected: `{summary['path']}`")

                if summary.get("code_verification"):
                    failed_checks = sum(
                        1 for item in summary["code_verification"] if item["failed"]
                    )
                    st.caption(
                        f"Code checks: {len(summary['code_verification'])} run, "
                        f"{failed_checks} failed"
                    )

                if summary["scores"]:
                    st.markdown("### Score history")
                    st.line_chart(
                        {"Score": summary["scores"]},
                        width="stretch",
                        height=200,
                    )

                if is_cloud_enabled():
                    st.info(
                        "Cloud fallback is enabled in config/models.yaml, but this "
                        "dashboard does not yet support the interactive cost/"
                        "approval flow (Phase 7's approval step reads from a "
                        "real terminal, which a background web request doesn't "
                        "have, and the real Anthropic adapter is still "
                        "unimplemented pending model/pricing verification -- see "
                        "docs/audits/2026-07-04-phase-7-maintainer-report.md). "
                        "Cloud escalation was not attempted for this run. Use "
                        "`python run.py --allow-cloud` from a terminal instead."
                    )

                metrics = summary.get("metrics") or {}

                validator_failures = metrics.get("validator_failures") or {}
                if validator_failures:
                    st.markdown("### Validator failures")
                    st.caption(
                        "A high Judge score cannot rescue a draft that violates "
                        "a checkable constraint (see docs/model-profiles.md)."
                    )
                    st.dataframe(
                        [{"rule": rule, "times failed": count}
                         for rule, count in validator_failures.items()],
                        width="stretch",
                        hide_index=True,
                    )

                if metrics.get("fallbacks"):
                    st.warning(
                        f"{metrics['fallbacks']} model fallback(s) occurred during "
                        "this run (a role's model timed out and a smaller local "
                        "model was used instead) -- output quality may be reduced "
                        "for that step. See the metrics summary below for details."
                    )

                with st.expander("Metrics summary (Phase 5)", expanded=False):
                    st.caption(
                        f"Total runtime: {metrics.get('total_elapsed_ms', 0) / 1000:.1f}s"
                    )
                    per_agent = metrics.get("per_agent") or {}
                    if per_agent:
                        st.dataframe(
                            [
                                {
                                    "role": role,
                                    "model": data.get("model"),
                                    "calls": data.get("calls"),
                                    "elapsed_ms": data.get("elapsed_ms"),
                                }
                                for role, data in per_agent.items()
                            ],
                            width="stretch",
                            hide_index=True,
                        )
                    calls_by_model = metrics.get("calls_by_model") or {}
                    if calls_by_model:
                        st.caption("Calls by model (confirms Phase 6's single-14B-family profiles in practice):")
                        st.dataframe(
                            [{"model": model, "calls": count}
                             for model, count in calls_by_model.items()],
                            width="stretch",
                            hide_index=True,
                        )
                    metric_cols = st.columns(3)
                    metric_cols[0].metric("Retries", metrics.get("retries", 0))
                    metric_cols[1].metric("Fallbacks", metrics.get("fallbacks", 0))
                    metric_cols[2].metric("Timeout events", metrics.get("timeout_events", 0))

                with st.expander("Role models used", expanded=False):
                    st.json(summary["role_models"])

        elif etype == "error":
            st.error(f"Pipeline error: {event['message']}")
            st.info("Check that Ollama is running and the selected model is downloaded.")
            break

    if thread.is_alive():
        thread.join(timeout=5)


# ── Run history panel ─────────────────────────────────────────────────────────

st.markdown("---")
st.markdown("## Recent runs")

stats = get_db_stats()
stat_a, stat_b, stat_c = st.columns(3)
stat_a.metric("Total runs", stats["total_runs"])
stat_b.metric("Passed runs", stats["passed_runs"])
stat_c.metric("Average score", f"{stats['average_score']}/100")

history_runs = load_all_runs(limit=10)
if not history_runs:
    st.info("No saved runs yet. Run the pipeline once to populate history.")
else:
    table_rows = []
    for item in history_runs:
        table_rows.append({
            "ID": item["id"],
            "Timestamp": item["timestamp"][:19],
            "Score": item["final_score"],
            "Passed": "Yes" if item["passed"] else "No",
            "Loops": item["iterations"],
            "Mode": item["mode"],
            "Goal": item["goal"][:80],
        })

    st.dataframe(table_rows, width="stretch", hide_index=True)

    selected_id = st.selectbox(
        "Open run details",
        options=[item["id"] for item in history_runs],
        format_func=lambda run_id: f"Run #{run_id}",
        key="history_run_selector",
    )

    selected_run = load_run_by_id(int(selected_id))
    if selected_run:
        with st.expander("Selected run details", expanded=False):
            st.markdown(f"**Goal:** {selected_run['goal']}")
            st.markdown(f"**Refined goal:** {selected_run['refined_goal']}")
            st.markdown(f"**Mode:** `{selected_run['mode']}`")
            st.markdown(f"**Final score:** `{selected_run['final_score']}/100`")
            st.markdown(f"**Passed:** {'Yes' if selected_run['passed'] else 'No'}")
            st.markdown(f"**Stop reason:** {selected_run['stop_reason']}")
            st.markdown(f"**Run dir:** `{selected_run['run_dir']}`")

            if selected_run.get("iterations_detail"):
                st.markdown("### Iterations")
                for item in selected_run["iterations_detail"]:
                    st.markdown(
                        f"**Iteration {item['iteration']} — score {item['score']}/100**"
                    )
                    st.caption(item.get("critique", "")[:500])

            st.markdown("### Final output")
            st.markdown(selected_run.get("final_output", "[not stored]"))

