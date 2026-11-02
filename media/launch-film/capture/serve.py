"""Start and stop the real dashboard for recording: app/streamlit_app.py from the scratch clone of
andyyaro/local-ai-orchestrator (main @0f3f321), on the README's address http://localhost:8501.

    python3 -I capture/serve.py start     # warms llama3.2:3b with one short call, starts Streamlit, waits for health
    python3 -I capture/serve.py stop      # stops Streamlit and unloads the model (ollama stop llama3.2:3b)
    python3 -I capture/serve.py status

The clone's config/models.yaml has active_profile: bootstrap (the documented switch: every role on llama3.2:3b) and a
fresh runs/ folder, so the dashboard's history is the film's run only (never Andy's own runs/history.db).
--theme.codeFont sans-serif is Streamlit's own config flag: without it the inline code (the profile name, "fast") and
st.json render in Source Code Pro, a monospace face the film may not show.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# The working folder (not kept): a clone of the repository in work/repo, its venv in work/venv, raw frames.
SCR = Path(__file__).resolve().parent.parent / "work"
REPO = SCR / "repo"
VENV = SCR / "venv"
PIDF = SCR / "streamlit.pid"
LOG = SCR / "streamlit-capture.log"
PORT = 8501
MODEL = "llama3.2:3b"


def healthy() -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/_stcore/health", timeout=2) as r:
            return r.read().strip() == b"ok"
    except Exception:
        return False


def warm() -> float:
    """One short generation so the model is resident before the take (the first call otherwise loads it)."""
    body = json.dumps({"model": MODEL, "prompt": "Say OK.", "stream": False, "keep_alive": "15m",
                       "options": {"num_predict": 4}}).encode()
    t0 = time.time()
    req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        json.loads(r.read())
    return time.time() - t0


def start() -> None:
    if healthy():
        print("streamlit already up on", PORT)
        return
    prof = [l for l in (REPO / "config" / "models.yaml").read_text().splitlines() if l.startswith("active_profile:")]
    assert prof == ["active_profile: bootstrap"], prof
    print(f"warm {MODEL}: {warm():.1f} s")
    cmd = [str(VENV / "bin" / "streamlit"), "run", "app/streamlit_app.py",
           "--server.address", "127.0.0.1", "--server.port", str(PORT), "--server.headless", "true",
           "--browser.gatherUsageStats", "false", "--server.fileWatcherType", "none",
           "--theme.codeFont", "sans-serif"]
    log = open(LOG, "a")
    p = subprocess.Popen(cmd, cwd=REPO, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    PIDF.write_text(str(p.pid))
    for _ in range(120):
        if healthy():
            print("streamlit up, pid", p.pid)
            return
        time.sleep(0.5)
    raise SystemExit("streamlit did not come up; see " + str(LOG))


def stop() -> None:
    if PIDF.exists():
        pid = int(PIDF.read_text().strip() or 0)
        try:
            os.killpg(pid, signal.SIGTERM)
            print("stopped streamlit", pid)
        except ProcessLookupError:
            pass
        PIDF.unlink()
    subprocess.run(["ollama", "stop", MODEL], check=False)
    print("ollama stop", MODEL)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    {"start": start, "stop": stop, "status": lambda: print("healthy" if healthy() else "down")}[cmd]()
