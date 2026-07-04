"""
app/streamlit_app.py

Streamlit dashboard for the Local AI Orchestrator.
Wraps the same pipeline agents as run.py in a local web interface.

Run with:
    streamlit run app/streamlit_app.py
"""

import json
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

from agents.builder import BuilderAgent
from agents.critic import CriticAgent
from agents.fixer import FixerAgent
from agents.judge import JudgeAgent
from agents.planner import PlannerAgent
from agents.supervisor import SupervisorAgent
from agents.synthesizer import SynthesizerAgent
from orchestrator.code_runner import verification_failed, verify_draft_code
from orchestrator.config_loader import get_active_profile, get_model_for_role
from orchestrator.database import get_db_stats, load_all_runs, load_run_by_id, save_run

RUNS_DIR = ROOT / "runs"
RUNS_DIR.mkdir(exist_ok=True)

DEFAULT_MAX_LOOPS = 3
DEFAULT_THRESHOLD = 70
DEFAULT_MIN_IMPROVEMENT = 5

FAST_ROLES = {"supervisor", "planner", "critic"}
MAIN_ROLES = {"builder", "fixer", "synthesizer"}


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_run_dir() -> Path:
    """Create a Streamlit-specific run folder under runs/."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RUNS_DIR / f"ui_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def save(run_dir: Path, filename: str, content: str):
    """Save one pipeline artifact into the active run folder."""
    (run_dir / filename).write_text(content, encoding="utf-8")


def score_bar(score: int, width: int = 40) -> str:
    filled = int(score / 100 * width)
    return "█" * filled + "░" * (width - filled)


def normalize_override(value: str) -> str | None:
    """Convert the UI's config-driven option into the None override used by code."""
    return None if value == "config-driven" else value


def role_model(
    role: str,
    mode: str,
    model_main: str | None,
    model_fast: str | None,
    model_judge: str | None,
) -> str:
    """Return the model for a role, honoring UI overrides when supplied."""
    if model_judge and role == "judge":
        return model_judge
    if model_fast and role in FAST_ROLES:
        return model_fast
    if model_main and role in MAIN_ROLES:
        return model_main
    if model_main and role == "judge":
        return model_main
    return get_model_for_role(role, mode)


def emit_step(event_queue: Queue, agent: str, status: str, output: str = ""):
    event_queue.put({
        "type": "step",
        "agent": agent,
        "status": status,
        "output": output,
    })


def collect_iterations(run_dir: Path, scores: list[int]) -> list[dict]:
    """Load saved loop artifacts so they can be stored in SQLite."""
    iterations_data = []
    for i, score in enumerate(scores, start=1):
        critique_path = run_dir / f"loop{i:02d}_critic.txt"
        fixer_path = run_dir / f"loop{i:02d}_fixer.txt"
        judge_path = run_dir / f"loop{i:02d}_judge.json"
        iterations_data.append({
            "iteration": i,
            "critique": (
                critique_path.read_text(encoding="utf-8")
                if critique_path.exists()
                else ""
            ),
            "revised_draft": (
                fixer_path.read_text(encoding="utf-8")
                if fixer_path.exists()
                else ""
            ),
            "verdict": (
                json.loads(judge_path.read_text(encoding="utf-8"))
                if judge_path.exists()
                else {}
            ),
            "score": score,
        })
    return iterations_data


def apply_code_verification_to_verdict(verdict: dict, code_feedback: str) -> dict:
    """Force a hard fail when coding-mode verification finds broken code."""
    if not code_feedback or not verification_failed(code_feedback):
        return verdict

    hard_fails = verdict.get("hard_fails", [])
    if not isinstance(hard_fails, list):
        hard_fails = []
    if "broken_code" not in hard_fails:
        hard_fails.append("broken_code")

    verdict["hard_fails"] = hard_fails
    verdict["pass"] = False
    verdict["total_score"] = 0
    verdict["rationale"] = (
        str(verdict.get("rationale", ""))
        + "\n\nCode verification failed before Judge pass/fail was accepted. "
        + "Broken or blocked code cannot pass regardless of model score."
    ).strip()
    verdict["code_verification"] = code_feedback
    return verdict


def should_break_on_hard_fail(
    mode: str,
    verdict: dict,
    iteration: int,
    max_loops: int,
) -> bool:
    """Allow coding-mode broken_code to continue until max loops."""
    hard_fails = verdict.get("hard_fails") or []
    if not hard_fails:
        return False
    if mode == "coding" and "broken_code" in hard_fails and iteration < max_loops:
        return False
    return True


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
    selected_mode: str,
    model_main: str | None,
    model_fast: str | None,
    model_judge: str | None,
    max_loops: int,
    threshold: int,
    min_improvement: int,
    run_dir: Path,
    event_queue: Queue,
):
    """
    Runs the full pipeline in a background thread and posts events to event_queue
    so the Streamlit UI can display each completed agent step.
    """
    try:
        summary = {
            "goal": goal,
            "active_profile": get_active_profile(),
            "model_main_override": model_main,
            "model_fast_override": model_fast,
            "model_judge_override": model_judge,
            "role_models": {},
            "threshold": threshold,
            "max_loops": max_loops,
            "iterations_run": 0,
            "scores": [],
            "code_verification": [],
            "stop_reason": "",
            "final_score": 0,
            "passed": False,
            "mode": selected_mode,
        }

        # Supervisor
        emit_step(event_queue, "Supervisor", "running")
        supervisor_model = role_model(
            "supervisor",
            "general",
            model_main,
            model_fast,
            model_judge,
        )
        summary["role_models"]["supervisor"] = supervisor_model
        supervisor = SupervisorAgent(model=supervisor_model)
        sup_result = supervisor.run(goal=goal)
        refined_goal = sup_result["refined_goal"]
        supervisor_mode = sup_result.get("mode", "general")
        sup_result["selected_mode"] = selected_mode
        save(run_dir, "00_supervisor.json", json.dumps(sup_result, indent=2))
        emit_step(
            event_queue,
            "Supervisor",
            "done",
            (
                f"Refined goal: {refined_goal}\n\n"
                f"Supervisor suggested mode: {supervisor_mode}\n\n"
                f"Selected UI mode: {selected_mode}"
            ),
        )

        # Planner
        emit_step(event_queue, "Planner", "running")
        planner_model = role_model(
            "planner",
            selected_mode,
            model_main,
            model_fast,
            model_judge,
        )
        summary["role_models"]["planner"] = planner_model
        planner = PlannerAgent(model=planner_model)
        plan = planner.run(goal=refined_goal, mode=selected_mode)
        save(run_dir, "01_planner_plan.txt", plan)
        emit_step(event_queue, "Planner", "done", plan)

        # Builder
        emit_step(event_queue, "Builder", "running")
        builder_model = role_model(
            "builder",
            selected_mode,
            model_main,
            model_fast,
            model_judge,
        )
        summary["role_models"]["builder"] = builder_model
        builder = BuilderAgent(model=builder_model)
        draft = builder.run(goal=refined_goal, plan=plan, mode=selected_mode)
        save(run_dir, "02_builder_draft_v0.txt", draft)
        emit_step(event_queue, "Builder", "done", draft)

        best_draft = draft
        best_score = 0
        previous_score = 0
        previous_code_feedback = ""
        stop_reason = f"max_loops ({max_loops}) reached"

        critic_model = role_model(
            "critic",
            selected_mode,
            model_main,
            model_fast,
            model_judge,
        )
        fixer_model = role_model(
            "fixer",
            selected_mode,
            model_main,
            model_fast,
            model_judge,
        )
        judge_model = role_model(
            "judge",
            selected_mode,
            model_main,
            model_fast,
            model_judge,
        )
        summary["role_models"].update({
            "critic": critic_model,
            "fixer": fixer_model,
            "judge": judge_model,
        })

        critic = CriticAgent(model=critic_model)
        fixer = FixerAgent(model=fixer_model)
        judge = JudgeAgent(model=judge_model, pass_threshold=threshold)

        for iteration in range(1, max_loops + 1):
            summary["iterations_run"] = iteration
            event_queue.put({
                "type": "loop_start",
                "iteration": iteration,
                "max_loops": max_loops,
            })

            emit_step(event_queue, f"Loop {iteration} Critic", "running")
            critique = critic.run(goal=refined_goal, draft=draft)
            if previous_code_feedback:
                critique += (
                    "\n\nCODE VERIFICATION FEEDBACK FROM PREVIOUS REVISION:\n"
                    f"{previous_code_feedback}\n"
                    "The next revision must fix these execution issues."
                )
            save(run_dir, f"loop{iteration:02d}_critic.txt", critique)
            emit_step(event_queue, f"Loop {iteration} Critic", "done", critique)

            emit_step(event_queue, f"Loop {iteration} Fixer", "running")
            revised = fixer.run(
                goal=refined_goal,
                draft=draft,
                critique=critique,
                iteration=iteration,
                mode=selected_mode,
            )
            save(run_dir, f"loop{iteration:02d}_fixer.txt", revised)
            emit_step(event_queue, f"Loop {iteration} Fixer", "done", revised)

            code_feedback = ""
            if selected_mode == "coding":
                emit_step(event_queue, f"Loop {iteration} Code Verification", "running")
                code_feedback = verify_draft_code(revised)
                code_run_file = f"loop{iteration:02d}_code_run.txt"
                save(run_dir, code_run_file, code_feedback)
                summary["code_verification"].append({
                    "iteration": iteration,
                    "failed": verification_failed(code_feedback),
                    "feedback_file": code_run_file,
                })
                emit_step(
                    event_queue,
                    f"Loop {iteration} Code Verification",
                    "done",
                    f"```text\n{code_feedback}\n```",
                )

            emit_step(event_queue, f"Loop {iteration} Judge", "running")
            verdict = judge.run(
                goal=refined_goal,
                draft=revised,
                iteration=iteration,
                mode=selected_mode,
            )
            if selected_mode == "coding":
                verdict = apply_code_verification_to_verdict(verdict, code_feedback)
            save(run_dir, f"loop{iteration:02d}_judge.json", json.dumps(verdict, indent=2))
            emit_step(
                event_queue,
                f"Loop {iteration} Judge",
                "done",
                f"```json\n{json.dumps(verdict, indent=2)}\n```",
            )

            score = int(verdict["total_score"])
            summary["scores"].append(score)

            code_failed = selected_mode == "coding" and verification_failed(code_feedback)
            if score > best_score and not code_failed:
                best_score = score
                best_draft = revised
                save(run_dir, "best_draft.txt", best_draft)

            event_queue.put({
                "type": "loop_result",
                "iteration": iteration,
                "score": score,
                "scores": summary["scores"].copy(),
                "passed": bool(verdict.get("pass")),
                "score_bar": score_bar(score),
            })

            if verdict.get("pass"):
                stop_reason = f"passed (score {score} >= threshold {threshold})"
                draft = revised
                break

            if iteration > 1:
                improvement = score - previous_score
                if improvement < min_improvement and not code_failed:
                    stop_reason = (
                        f"stalled (improvement {improvement} < "
                        f"min_improvement {min_improvement})"
                    )
                    draft = revised
                    break

            if should_break_on_hard_fail(selected_mode, verdict, iteration, max_loops):
                stop_reason = f"hard_fail: {verdict['hard_fails']}"
                draft = revised
                break

            previous_score = score
            previous_code_feedback = code_feedback
            draft = revised

        # Final Synthesizer
        emit_step(event_queue, "Synthesizer", "running")
        synthesizer_model = role_model(
            "synthesizer",
            selected_mode,
            model_main,
            model_fast,
            model_judge,
        )
        summary["role_models"]["synthesizer"] = synthesizer_model
        synthesizer = SynthesizerAgent(model=synthesizer_model)
        final_output = synthesizer.run(
            goal=refined_goal,
            best_draft=best_draft,
            score=best_score,
            iterations=summary["iterations_run"],
        )
        save(run_dir, "final_output.txt", final_output)
        emit_step(event_queue, "Synthesizer", "done", final_output)

        summary["stop_reason"] = stop_reason
        summary["final_score"] = best_score
        summary["passed"] = best_score >= threshold

        iterations_data = collect_iterations(run_dir, summary["scores"])
        db_run_id = save_run(
            goal=goal,
            refined_goal=refined_goal,
            mode=selected_mode,
            model_main=model_main or builder_model,
            model_fast=model_fast or critic_model,
            final_score=best_score,
            passed=(best_score >= threshold),
            stop_reason=stop_reason,
            scores=summary["scores"],
            run_dir=str(run_dir),
            final_output=final_output,
            iterations_data=iterations_data,
        )
        summary["db_run_id"] = db_run_id
        save(run_dir, "run_summary.json", json.dumps(summary, indent=2))

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

    mode = st.selectbox(
        "Mode",
        options=["general", "writing", "coding", "planning", "debugging", "study"],
        index=0,
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
                "gemma3:12b",
            ],
            index=0,
        )

        model_judge_choice = st.selectbox(
            "Judge model",
            options=[
                "config-driven",
                "phi4:14b",
                "llama3.1:8b",
                "llama3.2:3b",
            ],
            index=0,
        )

    render_status_pill("Local only", "green")

    if mode == "coding":
        with st.expander("Coding safety", expanded=False):
            st.caption(
                "Generated Python can be executed locally with a timeout and "
                "a safety blocklist. Review code before reusing it."
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
    model_judge = normalize_override(model_judge_choice)

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
            "selected_mode": mode,
            "model_main": model_main,
            "model_fast": model_fast,
            "model_judge": model_judge,
            "max_loops": max_loops,
            "threshold": threshold,
            "min_improvement": min_improvement,
            "run_dir": run_dir,
            "event_queue": event_queue,
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

