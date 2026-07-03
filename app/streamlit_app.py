"""
app/streamlit_app.py

Streamlit dashboard for the Local AI Orchestrator.
Wraps the same pipeline agents as run.py in a local web interface.

Run with:
    streamlit run app/streamlit_app.py
"""

import json
import sys
import time
import threading
from datetime import datetime
from pathlib import Path
from queue import Queue, Empty

import streamlit as st

# Make sure the project root is on sys.path so agents/ can be imported.
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.supervisor import SupervisorAgent
from agents.planner import PlannerAgent
from agents.builder import BuilderAgent
from agents.critic import CriticAgent
from agents.fixer import FixerAgent
from agents.judge import JudgeAgent
from agents.synthesizer import SynthesizerAgent
from orchestrator.config_loader import get_active_profile, get_model_for_role

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


def role_model(role: str, mode: str, model_main: str | None,
               model_fast: str | None, model_judge: str | None) -> str:
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


# ── Pipeline runner ──────────────────────────────────────────────────────────

def run_pipeline_thread(goal: str, selected_mode: str, model_main: str | None,
                        model_fast: str | None, model_judge: str | None,
                        max_loops: int, threshold: int, min_improvement: int,
                        run_dir: Path, event_queue: Queue):
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
            "stop_reason": "",
            "final_score": 0,
            "passed": False,
            "mode": selected_mode,
        }

        # Supervisor
        emit_step(event_queue, "Supervisor", "running")
        supervisor_model = role_model("supervisor", "general", model_main,
                                      model_fast, model_judge)
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
                f"**Refined goal:** {refined_goal}\n\n"
                f"**Supervisor suggested mode:** `{supervisor_mode}`\n\n"
                f"**Selected UI mode:** `{selected_mode}`"
            ),
        )

        # Planner
        emit_step(event_queue, "Planner", "running")
        planner_model = role_model("planner", selected_mode, model_main,
                                   model_fast, model_judge)
        summary["role_models"]["planner"] = planner_model
        planner = PlannerAgent(model=planner_model)
        plan = planner.run(goal=refined_goal, mode=selected_mode)
        save(run_dir, "01_planner_plan.txt", plan)
        emit_step(event_queue, "Planner", "done", plan)

        # Builder
        emit_step(event_queue, "Builder", "running")
        builder_model = role_model("builder", selected_mode, model_main,
                                   model_fast, model_judge)
        summary["role_models"]["builder"] = builder_model
        builder = BuilderAgent(model=builder_model)
        draft = builder.run(goal=refined_goal, plan=plan, mode=selected_mode)
        save(run_dir, "02_builder_draft_v0.txt", draft)
        emit_step(event_queue, "Builder", "done", draft)

        best_draft = draft
        best_score = 0
        previous_score = 0
        stop_reason = f"max_loops ({max_loops}) reached"

        critic_model = role_model("critic", selected_mode, model_main,
                                  model_fast, model_judge)
        fixer_model = role_model("fixer", selected_mode, model_main,
                                 model_fast, model_judge)
        judge_model = role_model("judge", selected_mode, model_main,
                                 model_fast, model_judge)
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

            emit_step(event_queue, f"Loop {iteration} Judge", "running")
            verdict = judge.run(
                goal=refined_goal,
                draft=revised,
                iteration=iteration,
                mode=selected_mode,
            )
            save(run_dir, f"loop{iteration:02d}_judge.json", json.dumps(verdict, indent=2))
            emit_step(event_queue, f"Loop {iteration} Judge", "done",
                      f"```json\n{json.dumps(verdict, indent=2)}\n```")

            score = int(verdict["total_score"])
            summary["scores"].append(score)

            if score > best_score:
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
                if improvement < min_improvement:
                    stop_reason = (
                        f"stalled (improvement {improvement} < "
                        f"min_improvement {min_improvement})"
                    )
                    draft = revised
                    break

            if verdict.get("hard_fails"):
                stop_reason = f"hard_fail: {verdict['hard_fails']}"
                draft = revised
                break

            previous_score = score
            draft = revised

        # Final Synthesizer
        emit_step(event_queue, "Synthesizer", "running")
        synthesizer_model = role_model("synthesizer", selected_mode, model_main,
                                       model_fast, model_judge)
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
        save(run_dir, "run_summary.json", json.dumps(summary, indent=2))

        event_queue.put({
            "type": "final",
            "output": final_output,
            "summary": summary,
            "run_dir": str(run_dir),
        })

    except Exception as exc:  # pragma: no cover - visible in UI during manual runs
        event_queue.put({"type": "error", "message": str(exc)})


# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Local AI Orchestrator",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Sidebar — configuration ──────────────────────────────────────────────────

with st.sidebar:
    st.title("⚙️ Configuration")
    st.caption(f"Active profile: `{get_active_profile()}`")

    model_main_choice = st.selectbox(
        "Builder / Fixer / Synthesizer model",
        options=[
            "config-driven",
            "qwen2.5:14b",
            "qwen2.5-coder:14b",
            "llama3.1:8b",
            "llama3.2:3b",
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

    model_fast_choice = st.selectbox(
        "Fast model (Supervisor / Planner / Critic)",
        options=[
            "config-driven",
            "llama3.2:3b",
            "llama3.1:8b",
            "gemma3:12b",
        ],
        index=0,
    )

    mode = st.selectbox(
        "Workflow mode",
        options=["general", "writing", "coding", "planning", "debugging", "study"],
        index=0,
    )

    max_loops = st.slider("Max improvement loops", min_value=1, max_value=6,
                          value=DEFAULT_MAX_LOOPS, step=1)
    threshold = st.slider("Pass threshold (score / 100)", min_value=50,
                          max_value=95, value=DEFAULT_THRESHOLD, step=5)
    min_improvement = st.slider("Min score gain before stall stop",
                                min_value=0, max_value=15,
                                value=DEFAULT_MIN_IMPROVEMENT, step=1)

    st.divider()
    st.caption("All models run locally via Ollama.")
    st.caption("No data is sent to external servers.")
    if mode in {"coding", "debugging"}:
        st.warning(
            "Coding/debugging mode may use qwen2.5-coder:14b from config. "
            "Do not select it until that model is installed."
        )


# ── Main area ────────────────────────────────────────────────────────────────

st.title("🧠 Local AI Orchestrator")
st.caption("Multi-agent quality loop · Runs entirely on your Mac · Powered by Ollama")

goal = st.text_area(
    "Enter your goal or task",
    placeholder=(
        "Example: Write a technical blog post explaining how attention mechanisms "
        "work in transformer models, suitable for a Python developer new to ML."
    ),
    height=120,
)

col1, col2 = st.columns([1, 4])
with col1:
    run_btn = st.button("▶  Run Pipeline", type="primary", use_container_width=True)
with col2:
    st.caption(
        "Runtime depends on selected models. Serious profile runs can take several "
        "minutes per loop; bootstrap/fast models are quicker."
    )

st.divider()


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

    st.subheader("📡 Live Pipeline Output")
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
                        f"⏳ {agent}...", expanded=False
                    )
                    agent_expanders[agent].write("Running...")
                elif status == "done" and agent in agent_expanders:
                    agent_expanders[agent].update(
                        label=f"✅ {agent}", state="complete", expanded=False
                    )
                    with agent_expanders[agent]:
                        st.markdown(output)

        elif etype == "loop_start":
            with output_placeholder:
                st.markdown(
                    f"---\n**🔄 Loop {event['iteration']} of {event['max_loops']}**"
                )

        elif etype == "loop_result":
            scores_so_far = event["scores"]
            with score_placeholder.container():
                st.subheader("📊 Score Progression")
                if len(scores_so_far) > 1:
                    st.line_chart(
                        {"Score": scores_so_far},
                        use_container_width=True,
                        height=200,
                    )
                elif scores_so_far:
                    st.metric("Current score", f"{scores_so_far[-1]}/100")
                    st.caption(f"Score bar: `{event['score_bar']}`")

        elif etype == "final":
            output = event["output"]
            summary = event["summary"]

            with final_placeholder.container():
                st.divider()
                st.subheader("✨ Final Output")
                st.markdown(output)
                st.download_button(
                    label="📥 Download final output",
                    data=output,
                    file_name="final_output.txt",
                    mime="text/plain",
                )

            with summary_placeholder.container():
                st.divider()
                st.subheader("📋 Run Summary")
                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.metric("Final score", f"{summary['final_score']}/100")
                col_b.metric("Passed", "Yes ✓" if summary["passed"] else "No ✗")
                col_c.metric("Loops run", summary["iterations_run"])
                col_d.metric("Mode", summary["mode"])

                st.caption(f"Stop reason: {summary['stop_reason']}")
                st.caption(f"Run saved to: {event['run_dir']}")

                if summary["scores"]:
                    st.subheader("Score history")
                    st.line_chart(
                        {"Score": summary["scores"]},
                        use_container_width=True,
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
