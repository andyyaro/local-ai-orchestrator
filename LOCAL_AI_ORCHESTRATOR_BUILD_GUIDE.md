# Local AI Orchestrator — Complete Build Guide

**MacBook Pro M3 · 24GB RAM · macOS Tahoe · Ollama · Python · LangGraph · Streamlit**

> This guide takes you from a fresh working directory to a fully operational local-first
> multi-agent AI orchestration system. It is written for someone who is comfortable with
> Terminal but wants every step spelled out explicitly — no assumed knowledge, no skipped
> commands, no hand-waving.

---

## How to use this guide

- Follow sections in order on your first build.
- Each section ends with a verification step. Do not skip them.
- Commands that could overwrite or delete data are marked with a ⚠️ warning.
- All file paths are absolute from your Mac's home directory (`~` = `/Users/andyyaro`).
- Command blocks are copy-paste friendly — commands do not include a `$` prompt prefix.
  Lines beginning with `#` inside command blocks are comments explaining the command,
  not part of the command itself.

---

# SECTION 1 — Project Overview

## What you are building

You are building a **local-first multi-agent AI orchestration system** that runs entirely
on your MacBook, with no paid API subscriptions and no internet connection required after the initial setup.

In plain English: you type one goal or prompt into the system, and instead of sending
that prompt to a single AI model and getting one answer back, the system passes your goal
through a **pipeline of specialized AI agents**, each with a different job. Each agent
calls a local model running through Ollama. The agents work in sequence, criticizing and
improving the output until it meets a quality bar you set, then returning a polished
final answer.

This is a serious productivity tool, not a toy. The same architecture that large AI
companies use in production (multi-agent loops with critique and revision) runs entirely
on your laptop, for free.

---

## What "multi-agent orchestration" means in this project

"Orchestration" means coordinating multiple independent agents so they work together
toward a shared goal. In this project:

- Each **agent** is a Python function that sends a prompt to a local model and returns
  the model's response.
- The **orchestrator** is the code that decides which agent runs next, what input it
  receives, and whether the loop should continue or stop.
- The agents do not run in parallel. They run **sequentially**: one finishes, its output
  becomes the next agent's input.
- You control the quality threshold. If the Judge agent scores the output below your
  threshold (e.g., 70/100), the loop repeats. If it passes, the Final Synthesizer
  polishes it and returns the result.

This is different from a simple chatbot. A chatbot gives you one response. This system
gives you a **revised, scored, and polished response** that went through multiple rounds
of self-critique before you see it.

---

## What each agent role does

### Supervisor
Receives your raw goal. Decides whether the goal is clear enough to proceed. If the
goal is ambiguous, it rewrites it into a cleaner problem statement. Acts as a gate:
nothing enters the pipeline without passing through the Supervisor.

**Input:** Your raw user goal.
**Output:** A refined problem statement and routing decision (which mode to use).

---

### Planner
Takes the refined problem statement and creates a step-by-step plan. For writing tasks,
the plan is an outline. For coding tasks, the plan is a pseudocode or architecture
sketch. For debugging tasks, the plan is a hypothesis list.

**Input:** Refined problem statement from the Supervisor.
**Output:** A structured plan with numbered steps.

---

### Builder
The main production agent. Takes the plan and builds the actual output: writes the
essay, writes the code, writes the explanation, etc. This is the first real draft.

**Input:** The plan from the Planner.
**Output:** Draft v1 of the final deliverable.

---

### Critic
Reviews the Builder's draft against the original goal. Identifies specific weaknesses:
logic gaps, missing sections, factual errors, code bugs, poor structure, vague
language. The Critic does not rewrite — it only reports what is wrong and why.

**Input:** The original goal + the Builder's draft.
**Output:** A structured critique with specific, actionable feedback.

---

### Fixer
Takes the Builder's draft and the Critic's feedback and produces an improved version.
The Fixer is not starting from scratch — it is revising. It must address every point the
Critic raised.

**Input:** Builder's draft + Critic's feedback.
**Output:** Revised draft v2 (or vN in later iterations).

---

### Judge
Scores the Fixer's revised output against a rubric appropriate to the task mode.
Returns structured JSON with individual category scores, a total score, a pass/fail
decision, any hard failures (dealbreakers), and a rationale.

**Input:** Original goal + revised draft from the Fixer.
**Output:** JSON score object.

---

### Final Synthesizer
Only runs when the Judge has passed the output (or the max loop count is reached).
Takes the best-scoring version and polishes it: improves formatting, smooths language,
adds structure, makes it presentation-ready.

**Input:** The highest-scoring draft.
**Output:** Final polished deliverable.

---

## Why models run sequentially on your MacBook

Your MacBook has 24GB of unified memory shared between the CPU and GPU. A single capable
local model (such as `mistral:7b` or `llama3.2:3b`) uses between 4GB and 8GB of RAM
when loaded. If you tried to run two or three models simultaneously, you would exhaust
your available memory, the Mac would start swapping to disk (which is orders of
magnitude slower than RAM), and the system would become unusably slow or crash.

Running sequentially means: one model loads, generates its response, and then Ollama
may keep it in RAM briefly before the next call. In practice, Ollama keeps recently
used models in memory for a configurable time (controlled by `OLLAMA_KEEP_ALIVE`).
The recommended default for this project is `5m` — models stay warm between
sequential agent calls within the same run, then unload after 5 minutes of inactivity.
Use `OLLAMA_KEEP_ALIVE=0` only as a troubleshooting step when memory pressure is high.

This trades speed for stability. Each agent call takes 10–90 seconds depending on the
model and prompt length, but the system stays stable and never crashes from memory
pressure.

---

## What the terminal MVP will do

The MVP (Minimum Viable Product) is a command-line Python script that:

1. Accepts a goal from you as a text input.
2. Passes it through the full agent pipeline: Supervisor → Planner → Builder → Critic
   → Fixer → Judge → repeat if needed → Final Synthesizer.
3. Prints each agent's output to the terminal in real time.
4. Saves every intermediate version to files in a `runs/` folder.
5. Prints the final polished output at the end.
6. Reports the loop count, final score, and stop reason.

You run it with a single command:
```bash
python run.py --goal "Write a technical blog post about local AI inference"
```

No web browser required. No paid APIs. After setup and model downloads, runs entirely offline.

---

## What the finished Streamlit version will do

After the terminal MVP works, you will add a local web interface that runs in your
browser at `http://localhost:8501`. From that interface you can:

- Type your goal into a text box.
- Choose a workflow mode (Writing, Coding, Planning, Debugging, etc.).
- Set the max number of improvement loops (default: 3).
- Set the quality threshold score (default: 75/100).
- Click "Run" and watch each agent's output appear in real time.
- See a score chart showing quality improvement across iterations.
- See the final output in a formatted box with a Copy button.
- Browse a history panel showing all past runs stored in SQLite.
- Re-open any past run to see its intermediate steps.

The Streamlit interface is entirely local — it runs on your Mac, connects to localhost,
and stores everything on disk. Nothing is sent to external servers.

---

## What "done" looks like for the MVP

You have a working MVP when:

- [ ] `python run.py --goal "your goal here"` runs without errors.
- [ ] The Supervisor, Planner, Builder, Critic, Fixer, and Judge all call the local
      model and return non-empty text.
- [ ] The loop repeats at least once when the Judge score is below threshold.
- [ ] The loop stops correctly when the score passes or max loops are reached.
- [ ] The Final Synthesizer runs and produces a polished output.
- [ ] All intermediate files are saved under `runs/<timestamp>/`.
- [ ] The terminal prints a clear summary: loop count, final score, stop reason.

---

## What "done" looks like for the full version

You have a complete system when:

- [ ] All of the above MVP criteria are met.
- [ ] The Streamlit dashboard runs and displays all agent outputs in real time.
- [ ] SQLite saves every run and you can browse history in the Streamlit UI.
- [ ] Workflow modes (Writing, Coding, Planning, Debugging, Study) are selectable
      from the UI and change prompts + scoring rubrics accordingly.
- [ ] Coding mode runs `pytest` on generated code and feeds errors back into the loop.
- [ ] The LangGraph version of the workflow runs correctly alongside the plain Python
      fallback version.
- [ ] The project is on GitHub with a professional README, `.gitignore`, and clean
      commit history.
- [ ] The config files (`models.yaml`, `modes.yaml`) allow you to swap models without
      touching Python code.
- [ ] The model adapter layer is designed so that an OpenAI or Anthropic provider can
      be plugged in later by changing one config value (no API is used by default).

---

# SECTION 2 — Hardware Reality Check

## Your MacBook Pro M3 with 24GB unified memory

Your Mac uses **Apple Silicon unified memory architecture**. Unlike a traditional PC
where the CPU has its own RAM and a dedicated GPU has its own VRAM, your M3 chip shares
one pool of memory between CPU, GPU, and Neural Engine. This is important for local AI:
it means your GPU can use all 24GB for model inference, not just a separate fixed GPU
memory card.

This makes your MacBook significantly more capable for local AI than most PCs with
equivalent specs. A PC would need a discrete GPU with 16–24GB of VRAM to match what
your M3 chip can do natively.

---

## What model sizes are realistic

Think in terms of **parameter count** (billions of parameters, abbreviated "B") and
**quantization** (how compressed the model weights are, abbreviated "Q").

The practical rule is: **each billion parameters requires approximately 0.5–0.75GB of
RAM at 4-bit quantization (Q4), and approximately 1GB at 8-bit quantization (Q8).**

For your 24GB system (leave ~4GB for macOS and other processes, so ~20GB available for
models):

| Model Size | Quantization | Approx RAM | Fits in 20GB? | Speed on M3 |
|------------|-------------|------------|----------------|-------------|
| 1B–3B      | Q4          | 1–2.5 GB   | Yes, easily    | Very fast (1–5s) |
| 7B–8B      | Q4          | 4–5 GB     | Yes            | Fast (10–30s) |
| 13B        | Q4          | 7–8 GB     | Yes            | Moderate (30–60s) |
| 14B        | Q4          | 8–9 GB     | Yes            | Moderate (30–60s) |
| 27B        | Q4          | 14–16 GB   | Tight (yes)    | Slow (60–120s) |
| 32B        | Q4          | 18–20 GB   | Marginal       | Very slow (2–5 min) |
| 70B        | Q4          | 38–42 GB   | No             | Will swap/crash |

**Recommendation for this project:** Start with the Bootstrap profile (3B, ~2.5 GB RAM)
to verify the full pipeline works end-to-end, then switch to the Serious Work profile
for output you would actually use. The Serious Work profile uses multiple 12B–14B models
on disk (~35–40 GB total), but because agents run sequentially, only one model is loaded
at a time — peak loaded RAM is approximately 8–9 GB per model, not all models at once. Section 6 defines the four
profiles in detail. The key insight: 14B models fit comfortably on your 24GB system
and produce meaningfully better output than 7B models on complex writing and reasoning
tasks — they are not reserved for "someday"; they are the real target.

---

## What model sizes are NOT realistic

- **70B+ models:** These require 38–42GB at Q4 — nearly double your total RAM. Do not
  attempt them. Ollama will try to load them and your Mac will become unresponsive as it
  swaps to disk, potentially for minutes or until you force-quit.

- **Two 13B+ models simultaneously:** Even if each one fits individually, loading two
  13B models at the same time would require 16GB, leaving only 8GB for macOS and
  everything else. This will cause memory pressure.

- **Unquantized (FP16/FP32) large models:** A 7B model in FP16 requires ~14GB. Always
  use quantized versions (Q4 or Q8). Ollama defaults to Q4 for most models, so this
  usually handles itself automatically.

---

## Why RAM matters more than storage

Storage (your 1TB SSD) is where the model files live on disk. RAM is where the model
lives when it is actively running. When you call a model:

1. Ollama reads the model file from your SSD into RAM.
2. The model runs entirely in RAM during inference.
3. After inference, Ollama may keep the model in RAM briefly (controlled by
   `OLLAMA_KEEP_ALIVE`).

Your 1TB SSD is more than enough — a large collection of models (say, 10 different
7B–13B models) might use 50–80GB of disk space. That is 8% of your total storage.

RAM is the real constraint. If the model does not fit in RAM, it cannot run properly.
There is no workaround except using a smaller model or a more aggressively quantized
version.

---

## Why you should NOT try to run giant models locally

Beyond the hardware constraint, there is a diminishing returns problem. For multi-agent
orchestration, **output quality is more about prompt engineering and pipeline design
than raw model size.** A well-prompted 7B model in a critique-revise loop will often
produce better output than a single call to a 70B model with a weak prompt.

In this pipeline, you are essentially giving a smaller model multiple chances to improve
its answer, with structured guidance at each step. This compensates effectively for
what smaller models lack in one-shot quality.

This project's Serious Work profile puts 14B models on Builder, Critic, Judge, and
Synthesizer — the roles where quality is the bottleneck. The 8B model handles
Supervisor and Planner (routing decisions, not creative work). See Section 6 for the
exact assignment and the reasoning behind which model family goes to which role.

---

## Why you should avoid parallel large-model execution

If you run two 7B model calls at the same time:
- Both models try to load into RAM simultaneously.
- Total RAM usage doubles (10GB instead of 5GB).
- The GPU queues become contested.
- Response times slow down for both calls.
- Memory pressure increases, potentially causing macOS to compress memory pages.

This project runs agents **sequentially on purpose.** There is no performance benefit
to parallelism here because each agent's output is the next agent's input — they are
inherently dependent. Running them sequentially is not a limitation; it is the
correct architecture for this pipeline.

---

## What performance expectations you should have

**Bootstrap profile (3B — `llama3.2:3b`):**
- Each agent call: 3–10 seconds.
- Full pipeline: 1–2 minutes per loop.
- Use for verifying the pipeline works, not for final output.

**Fast profile (8B — `llama3.1:8b`):**
- First call after model load: 10–20 seconds (loading from disk + inference).
- Subsequent calls to the same model: 5–15 seconds (model cached in RAM).
- Each loop iteration (Builder → Critic → Fixer → Judge): ~60–120 seconds total.

**Serious Work / Coding profiles (14B — `qwen2.5:14b`, `phi4:14b`):**
- First call: 20–50 seconds.
- Each agent call: 20–50 seconds (different 14B models reload between roles).
- Full loop iteration with 3 × 14B agents: ~3–6 minutes.
- A 3-loop run: 10–20 minutes total.

These are real-world estimates on M3 24GB. Actual times vary with prompt length,
output length, and whether Ollama has the model cached in RAM from the previous call.

---

## What settings to use to avoid memory pressure

### Set OLLAMA_KEEP_ALIVE appropriately

By default, Ollama keeps a model in memory for 5 minutes after the last call. For
sequential pipeline calls where you are calling different agents in the same pipeline
run, you want the model to stay loaded between calls (saves reload time). However,
when the pipeline is done, you want the model to unload so RAM is freed.

The recommended setting for all profiles is `OLLAMA_KEEP_ALIVE=5m` (set permanently
in `~/.zshrc`, explained in Section 4.12). This keeps each model warm between sequential
agent calls within the same pipeline run, then unloads it after 5 minutes of inactivity.
Because agents run one at a time, at most one large model is in RAM at any moment.

Use `OLLAMA_KEEP_ALIVE=0` only as a troubleshooting step when memory pressure is high
or you see multiple models accumulating in RAM:

```bash
# Troubleshooting only — forces immediate unload after each call
export OLLAMA_KEEP_ALIVE=0
```

Or set it permanently in `~/.zshrc` (explained in Section 5).

### Close memory-hungry background apps

Before a long pipeline run, close:
- Browser tabs with video or heavy JS (each Chrome tab can use 200MB–1GB).
- Any other AI tools or large apps.
- Xcode if you have it open and are not using it.

You do not need to close VS Code — it uses ~300–500MB, which is fine.

---

## How to tell if your Mac is under memory pressure

### Method 1: Activity Monitor

1. Press `Command + Space` to open Spotlight.
2. Type `Activity Monitor` and press Enter.
3. Click the **Memory** tab.
4. Look at the bottom bar: "Memory Pressure".
   - **Green:** Normal. Fine to run models.
   - **Yellow:** Moderate pressure. Consider closing some apps.
   - **Red:** High pressure. Do not run large models. Close apps first.
5. Also check "Swap Used" — if swap is above 1–2GB, your Mac is using disk as
   overflow memory, which will make model responses very slow.

### Method 2: Terminal command

```bash
# Shows memory stats including swap usage and memory pressure level
vm_stat
```

What to look at in the output:
- `Pages free`: how many 16KB pages are unallocated (more is better).
- `Pages swapped out`: if this is high and increasing, you have memory pressure.

### Method 3: During a model run

Watch the Ollama process in Activity Monitor's Memory tab. A 7B model should use
about 4–5GB. If you see it using 12GB+ and your Mac fans start spinning loudly, the
model is too large or too many things are in memory.

---

## What to do if model responses are too slow

**Step 1: Check which model is running.** Large models are slow. Try the 3B version:
```bash
# Pull the smaller 3B variant
ollama pull llama3.2:3b

# Test it directly
ollama run llama3.2:3b "Write one sentence about cats."
```

**Step 2: Check memory pressure.** Open Activity Monitor and look at the Memory tab.
If pressure is yellow or red, close other apps.

**Step 3: Check if the model is loading from disk every time.** If each call takes
30+ seconds and you are calling the same model repeatedly, the model may be unloading
between calls. Check your `OLLAMA_KEEP_ALIVE` setting and increase it:
```bash
export OLLAMA_KEEP_ALIVE=10m
```

**Step 4: Reduce prompt length.** Longer prompts with more context take longer to
process. In the early MVP, keep prompts focused and concise.

**Step 5: Lower the quality threshold or max loops for testing.** During development,
set `MAX_LOOPS=1` and `PASS_THRESHOLD=50` so the pipeline completes quickly. Once the
system works end-to-end, increase the threshold.

**Step 6: Use a model with a smaller context window call.** By default, Ollama may
use a large context window (4096–8192 tokens). For shorter tasks, you can override
this in the Ollama API call with `"num_ctx": 2048` to reduce memory usage.

---

*End of Sections 1 and 2.*

---

# SECTION 3 — Verify Existing Tools

Before installing anything new, confirm exactly what you already have and whether it
is working. Run each command below in Terminal (`Command + Space`, type `Terminal`,
press Enter). Do not skip a check just because you think something is installed —
version mismatches and broken PATH entries are the most common source of early
problems.

---

## 3.1 Check Homebrew

```bash
brew --version
```

**What this does:** Prints the installed version of Homebrew, the macOS package
manager. If the command is found and returns a version, Homebrew is working.

**Expected output:**
```
Homebrew 4.x.x
```

**If it fails:** You see `command not found: brew`.
Fix: Homebrew is not in your PATH or not installed. To install it:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
After installing on Apple Silicon, Homebrew lives at `/opt/homebrew/bin/brew`. If
`brew` is still not found after installation, add it to your PATH:
```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zshrc
source ~/.zshrc
```
Then run `brew --version` again.

---

## 3.2 Check Python version

```bash
python3 --version
```

**What this does:** Prints the version of Python 3 on your PATH. You expect to see
Python 3.14.0 since that is what you installed.

**Expected output:**
```
Python 3.14.0
```

**Also check where Python lives:**
```bash
which python3
```

**Expected output** (example — path may vary by install method):
```
/usr/local/bin/python3
```
or
```
/opt/homebrew/bin/python3
```

**If `python3 --version` fails:** `python3` is not on your PATH. If you installed
Python from python.org, it may be at `/Library/Frameworks/Python.framework/Versions/3.14/bin/python3`.
Add it to PATH:
```bash
echo 'export PATH="/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
python3 --version
```

**Note about `python` vs `python3`:** On modern macOS, `python` (no number) may point
to Python 2 or nothing. Always use `python3` explicitly, or activate a virtual
environment (covered in Section 5) where `python` correctly points to Python 3.

---

## 3.3 Check pip

```bash
pip3 --version
```

**What this does:** Prints the version of pip (Python's package installer) and which
Python installation it belongs to.

**Expected output:**
```
pip 24.x.x from /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/pip (python 3.14)
```

The important part is that the Python version at the end matches your Python 3.14
install. If it says `python 3.9` or `python 2.7`, pip is pointing to a different
Python.

**If pip3 is not found:**
```bash
python3 -m ensurepip --upgrade
```
This command tells Python to install pip into itself. Run `pip3 --version` again
after.

---

## 3.4 Check Git

```bash
git --version
```

**What this does:** Prints the installed version of Git, the version control tool.

**Expected output:**
```
git version 2.x.x
```

**If Git is not found:** macOS will prompt you to install Xcode Command Line Tools
automatically when you first run a git command. Allow it. Alternatively:
```bash
xcode-select --install
```
A dialog box will appear asking you to install developer tools. Click Install. This
takes a few minutes. After it finishes, run `git --version` again.

**Also configure Git with your name and email** (required before making commits).
Even if Git is installed, check whether it is configured:
```bash
git config --global user.name
git config --global user.email
```

If these return nothing, set them now (replace with your actual name and email):
```bash
git config --global user.name "Your Name"
git config --global user.email "your@email.com"
```

---

## 3.5 Check VS Code command-line launcher

```bash
code --version
```

**What this does:** Checks whether the VS Code `code` command is available in
Terminal, which lets you open files and folders in VS Code from the command line.

**Expected output:**
```
1.9x.x
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
x64
```

**If `code` is not found:**
1. Open VS Code (from Applications or Spotlight).
2. Press `Command + Shift + P` to open the Command Palette.
3. Type `Shell Command: Install 'code' command in PATH`.
4. Press Enter and click Install if prompted.
5. Close and reopen Terminal, then run `code --version` again.

---

## 3.6 Check Ollama CLI

```bash
ollama --version
```

**What this does:** Prints the version of the Ollama command-line client. This checks
whether the CLI binary exists and is on your PATH.

**Expected output (when server is NOT running):**
```
Warning: could not connect to a running Ollama instance
Warning: client version is 0.12.9
```

**Expected output (when server IS running):**
```
ollama version is 0.12.9
```

The version number is fine either way — the "could not connect" warning just means
the Ollama server daemon is not running yet. The CLI itself is installed correctly.
Section 4 covers how to start the server.

**If `ollama` is not found at all:** The CLI is not installed or not on your PATH.
Check `/usr/local/bin/ollama`:
```bash
ls /usr/local/bin/ollama
```
If it exists, add `/usr/local/bin` to your PATH:
```bash
echo 'export PATH="/usr/local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```
If it does not exist, reinstall Ollama from https://ollama.com/download — download
the macOS `.dmg`, open it, drag Ollama to Applications, and launch it once to
complete setup.

---

## 3.7 Check whether the Ollama server is running

```bash
curl http://localhost:11434
```

**What this does:** Sends an HTTP request to port 11434 on your local machine, which
is where the Ollama server listens. If the server is running, it responds with a
short text message.

**Expected output (server IS running):**
```
Ollama is running
```

**Expected output (server is NOT running):**
```
curl: (7) Failed to connect to localhost port 11434 after 0 ms: Connection refused
```

This tells you exactly what is happening: the Ollama server process is not running.
Section 4 shows you how to fix this.

**Alternative check using Ollama directly:**
```bash
ollama list
```

**Expected output (server running, no models downloaded yet):**
```
NAME    ID    SIZE    MODIFIED
```

**Expected output (server not running):**
```
Error: could not connect to ollama app, is it running?
```

---

## Section 3 Verification Summary

Run this sequence quickly to get a full status overview:
```bash
echo "=== Homebrew ===" && brew --version
echo "=== Python ===" && python3 --version && which python3
echo "=== pip ===" && pip3 --version
echo "=== Git ===" && git --version
echo "=== VS Code ===" && code --version
echo "=== Ollama CLI ===" && ollama --version
echo "=== Ollama Server ===" && curl -s http://localhost:11434 || echo "Server not running"
```

**What this does:** Runs all seven checks in one shot and labels each output.

If every line above returns a version number or "Ollama is running", you are ready
to proceed. The only expected failure at this stage is the Ollama server check —
fix that in the next section.

---

# SECTION 4 — Fix or Complete Ollama Setup

You have the Ollama CLI installed (version 0.12.9) but the server is not running.
The server is a separate process that needs to be started before any model can be
called. Think of the CLI as a remote control and the server as the device it
controls — the remote exists, but you need to turn on the device.

---

## 4.1 Understand the two parts of Ollama

- **Ollama CLI (`ollama`):** The command-line tool you already have. You use it to
  pull models, run one-off prompts, and list models.
- **Ollama server (`ollama serve`):** A background HTTP server that listens on port
  11434. It loads models, runs inference, and responds to API calls. Your Python
  scripts will call this server.

The server can be started two ways:
1. By launching the **Ollama macOS app** (which starts the server automatically in
   the background).
2. By running **`ollama serve`** directly in a Terminal window.

For day-to-day use, the macOS app is recommended. For development and debugging,
`ollama serve` in a Terminal window is useful because you can see its logs in real
time.

---

## 4.2 How to start the Ollama app on macOS

**Option A — From Finder:**
1. Open Finder (`Command + N` or click the Finder icon in your Dock).
2. Click **Applications** in the left sidebar.
3. Find **Ollama** in the list and double-click it.
4. You will see a small llama icon appear in your Mac's menu bar (top-right area,
   near the clock).
5. That icon means the Ollama server is running.

**Option B — From Spotlight:**
1. Press `Command + Space`.
2. Type `Ollama`.
3. Press Enter.

**Option C — From Terminal (launch the app from command line):**
```bash
open -a Ollama
```
**What this does:** Tells macOS to open the Ollama application bundle, which starts
the server automatically.

---

## 4.3 How to verify Ollama is running after starting it

Wait 5–10 seconds after opening the app, then run:
```bash
curl http://localhost:11434
```

**Expected output:**
```
Ollama is running
```

Also check:
```bash
ollama list
```

This should now return without an error (even if the model list is empty because you
have not downloaded any models yet).

---

## 4.4 How to start Ollama from Terminal using `ollama serve`

Use this method when you want to see server logs in real time, which is helpful for
debugging. Open a **new Terminal window** (do not use the same window you are
running your Python scripts in) and run:

```bash
ollama serve
```

**What this does:** Starts the Ollama server in the foreground. It will print log
lines as models are loaded and requests come in. It will keep running until you
press `Control + C` to stop it.

**Important:** Do not run `ollama serve` if the Ollama app is already running —
that would try to start a second server on port 11434 and fail with a "bind: address
already in use" error. See Section 4.8 for how to handle that.

Leave this Terminal window open while you work. Open a second Terminal window for
running your Python scripts.

---

## 4.5 What macOS permission prompts you might see

When you first launch Ollama:

- **"Ollama wants to accept incoming network connections"** — Click **Allow**. Ollama
  needs this to serve requests on localhost.
- **"Allow Ollama to access the network?"** (may appear as a firewall dialog) — Click
  **Allow**.
- Gatekeeper may ask you to confirm opening an app from the internet the first time —
  click **Open**.

These prompts only appear once. After you allow them, Ollama will start without
prompts in the future.

---

## 4.6 How to stop Ollama

**If you are using the macOS app:**
1. Click the llama icon in the menu bar (top right of your screen).
2. Click **Quit Ollama**.

Or from Terminal:
```bash
pkill -f "ollama"
```
**What this does:** Sends a termination signal to any process whose name contains
"ollama". Use with care — it will stop both the app and any `ollama serve` process.

**If you started with `ollama serve`:** Press `Control + C` in the Terminal window
where it is running.

---

## 4.7 How to restart Ollama

```bash
# Stop any running Ollama process
pkill -f "ollama"

# Wait 2 seconds to let the port close
sleep 2

# Start again via app
open -a Ollama
```

Then verify it is running:
```bash
curl http://localhost:11434
```

---

## 4.8 What to do if port 11434 is unavailable

**Symptom:** You run `ollama serve` and see:
```
Error: listen tcp 127.0.0.1:11434: bind: address already in use
```

**Cause:** Something is already listening on port 11434 — either another Ollama
instance or a different process.

**Find what is using the port:**
```bash
lsof -i :11434
```
**What this does:** Lists open files/connections associated with port 11434, including
the process name and PID (process ID).

**Expected output if Ollama is already running:**
```
COMMAND   PID      USER   FD   TYPE ...
ollama   12345  andyyaro  ...
```

If the process is `ollama`, you already have an Ollama server running. Do not start
another one — just use the existing one. Verify with:
```bash
curl http://localhost:11434
```

If something else is using port 11434 (unusual), you can either stop that process or
change Ollama's port by setting an environment variable:
```bash
OLLAMA_HOST=127.0.0.1:11435 ollama serve
```
Then in your Python code, use `http://localhost:11435` instead of the default.

---

## 4.9 What to do if Ollama is installed but broken

**Symptom:** `ollama --version` returns a version but `curl http://localhost:11434`
always fails even after starting the app.

**Step 1:** Quit all Ollama instances:
```bash
pkill -f "ollama"
sleep 2
```

**Step 2:** Check if the Ollama app exists in Applications:
```bash
ls /Applications/Ollama.app
```
If it does not exist, the app was not properly installed. Reinstall:
1. Go to https://ollama.com/download
2. Download the macOS `.dmg`.
3. Open the `.dmg` and drag Ollama to your Applications folder.
4. Launch it from Applications.

**Step 3:** If the app exists but still does not start the server, try running the
server binary directly:
```bash
/Applications/Ollama.app/Contents/MacOS/ollama serve
```
**What this does:** Runs the Ollama server executable directly from inside the app
bundle, bypassing the GUI app wrapper. This is useful for debugging startup failures.

**Step 4:** Check for startup errors in the macOS system log:
```bash
log show --predicate 'process == "ollama"' --last 5m
```
**What this does:** Shows the last 5 minutes of macOS system log entries for the
ollama process. Look for error messages that explain why it failed to start.

---

## 4.10 Should you use the macOS app or `ollama serve`?

| Situation | Use |
|-----------|-----|
| Day-to-day work and pipeline runs | macOS app (starts automatically, stays running) |
| Debugging model load errors | `ollama serve` (see live logs) |
| Running headless on a server | `ollama serve` |
| Testing different port configurations | `ollama serve` with env vars |

**Recommendation for this project:** Use the macOS app for daily use. When debugging
issues with models or pipeline calls, stop the app and use `ollama serve` in a
terminal window so you can see exactly what the server is doing.

---

## 4.11 How to avoid duplicate Ollama instances

The most common mistake is running `ollama serve` in Terminal while the Ollama app
is also running. This causes port conflicts.

**Before running `ollama serve`, always check:**
```bash
curl http://localhost:11434
```

If it returns `Ollama is running`, a server is already active. Do not start another.

**To check all running Ollama processes:**
```bash
ps aux | grep ollama | grep -v grep
```
**What this does:** Lists all running processes and filters for lines containing
"ollama", excluding the grep command itself.

If you see more than one line, you have duplicate instances. Kill all of them:
```bash
pkill -f "ollama"
```
Then start fresh with one method (app or `ollama serve`).

---

## 4.12 Setting OLLAMA_KEEP_ALIVE permanently

To control how long models stay in memory after each call, add this to your shell
config. Open `~/.zshrc` in VS Code:

```bash
code ~/.zshrc
```

Add this line at the bottom (you can change the value later):
```bash
export OLLAMA_KEEP_ALIVE=5m
```

**What this means:** Models stay loaded in RAM for 5 minutes after the last call.
If you make another call within 5 minutes, the model is already warm and responds
faster. After 5 minutes of inactivity, the model is unloaded, freeing RAM.

Save the file, then reload your shell:
```bash
source ~/.zshrc
```

**What `source ~/.zshrc` does:** Reloads your shell configuration file so the new
environment variable takes effect in the current Terminal window without needing to
open a new one.

---

# SECTION 5 — Python Environment Setup

## 5.1 Should Python 3.14 work for this project?

Python 3.14.0 was released in late 2024 and is a relatively new version. The
packages this project uses — `langgraph`, `langchain-ollama`, `streamlit`,
`requests`, `pyyaml` — are all actively maintained and should support Python 3.14.

However, Python 3.14 occasionally has compatibility issues with packages that use
compiled C extensions (like some versions of `numpy`, `pydantic`, or `grpcio`) if
those packages have not yet published binary wheels for 3.14. When you try to
install a package without a pre-built wheel, pip will attempt to compile it from
source — which can fail if the right build tools are not present.

**The safe approach:**
1. Try creating a virtual environment with Python 3.14 and installing all packages.
2. If any package fails to install, switch to Python 3.12 (stable, universally
   supported) installed via Homebrew — see Section 5.8.

Do not change your system Python installation. Always use virtual environments.

---

## 5.2 How to create a virtual environment

A virtual environment is an isolated Python installation for one project. Packages
you install inside the virtual environment do not affect your system Python or other
projects, and vice versa.

First, make sure you are in your project directory:
```bash
cd ~/Downloads/multi-modal-workflow
```
**What `cd` does:** Changes your current directory to the project folder.

Create the virtual environment:
```bash
python3 -m venv .venv
```
**What this does:** Runs Python's built-in `venv` module to create a virtual
environment in a folder called `.venv` inside your project directory. The `.venv`
folder will contain a private copy of Python and pip.

Verify it was created:
```bash
ls -la .venv/
```
You should see folders: `bin`, `include`, `lib`, `pyvenv.cfg`.

---

## 5.3 How to activate the virtual environment

```bash
source .venv/bin/activate
```

**What this does:** Runs the activation script inside `.venv/bin/`, which modifies
your current shell session so that `python` and `pip` commands now refer to the
versions inside `.venv` instead of your system Python.

**After activation, your prompt changes** to show the environment name:
```
(.venv) andyyaro@MacBook-Pro multi-modal-workflow %
```

The `(.venv)` prefix is the confirmation that the environment is active.

**Important:** You must activate the virtual environment every time you open a new
Terminal window to work on this project. It does not stay active across sessions.
Section 5.9 shows how to make VS Code do this automatically.

---

## 5.4 How to confirm the environment is active

```bash
which python
```

**Expected output (environment active):**
```
/Users/andyyaro/Downloads/multi-modal-workflow/.venv/bin/python
```

If you see `/usr/bin/python` or `/opt/homebrew/bin/python`, the environment is not
active. Run `source .venv/bin/activate` again.

Also confirm the Python version inside the environment:
```bash
python --version
```
This should return `Python 3.14.0` (or whatever version was used to create the venv).

---

## 5.5 How to deactivate the virtual environment

When you are done working on this project and want to return to normal shell behavior:
```bash
deactivate
```

The `(.venv)` prefix will disappear from your prompt.

---

## 5.6 How to install dependencies

With the virtual environment active, install the core packages for the MVP:

```bash
pip install requests pyyaml
```
**What this does:** Installs the `requests` library (for calling the Ollama HTTP API)
and `pyyaml` (for reading YAML config files). These are the only two packages needed
for the plain Python terminal MVP.

Check they installed correctly:
```bash
python -c "import requests, yaml; print('OK')"
```
**What this does:** Runs a one-line Python script that imports both packages. If it
prints `OK`, the packages are available. If you see an `ImportError`, the install
failed.

---

## 5.7 What should go in `requirements.txt`

A `requirements.txt` file lists every Python package your project needs so that
anyone (including you, on a new machine) can recreate the environment with one
command.

Create the file:
```bash
code requirements.txt
```

Add the following content (this is the full list for the complete project, not just
the MVP — you will add packages as you build each phase):

```
# Core HTTP and config
requests>=2.31.0
pyyaml>=6.0.1

# LangGraph and LangChain Ollama integration (Phase 5)
langgraph>=0.2.0
langchain-ollama>=0.1.0
langchain-core>=0.2.0

# Streamlit dashboard (Phase 6)
streamlit>=1.35.0

# Database (Phase 7)
# sqlite3 is built into Python — no install needed

# Development tools
pytest>=8.0.0
black>=24.0.0
```

Save the file. Comments (lines starting with `#`) are ignored by pip.

**Install everything at once:**
```bash
pip install -r requirements.txt
```
**What this does:** Reads `requirements.txt` and installs every package listed in it.

**If any package fails:** Note which one and skip to Section 5.8 before trying
anything else.

---

## 5.8 How to freeze your exact installed versions

After successfully installing packages, save a snapshot of exact versions:
```bash
pip freeze > requirements-lock.txt
```
**What this does:** Writes every installed package and its exact version to
`requirements-lock.txt`. This is used for reproducibility — someone else installing
from `requirements-lock.txt` will get the exact same package versions you have.

**Do not commit `requirements-lock.txt` as your primary requirements file.** Keep
`requirements.txt` for human-readable minimum versions, and `requirements-lock.txt`
as a reference. Both can be committed to GitHub.

---

## 5.9 What to do if packages fail on Python 3.14

If `pip install -r requirements.txt` fails with an error like:
```
error: legacy-install-failure
  × Encountered error while trying to install package 'grpcio'
```
or:
```
note: This error originates from a subprocess, and is likely not a problem with pip.
```

This means a package does not have a pre-built binary for Python 3.14 and failed to
compile from source. The fix is to use Python 3.12 instead.

**Do not uninstall Python 3.14.** Install 3.12 alongside it using Homebrew:

```bash
# Install Python 3.12 via Homebrew
brew install python@3.12
```
**What this does:** Downloads and installs Python 3.12 into
`/opt/homebrew/bin/python3.12`. It does not touch your existing Python 3.14
installation.

Verify it installed:
```bash
python3.12 --version
```
**Expected output:**
```
Python 3.12.x
```

Now recreate the virtual environment using Python 3.12:

⚠️ **Warning:** The next command deletes the `.venv` folder and recreates it. Any
packages you already installed will be removed from the environment (not from your
system). You will need to `pip install` again after.

```bash
# Deactivate first if the environment is active
deactivate

# Remove the old environment
rm -rf .venv

# Create a new environment with Python 3.12
python3.12 -m venv .venv

# Activate it
source .venv/bin/activate

# Confirm the Python version
python --version
```
**Expected output:** `Python 3.12.x`

Now install packages again:
```bash
pip install -r requirements.txt
```
This should succeed on Python 3.12 because all major packages have pre-built wheels
for it.

---

## 5.10 How to make VS Code use the correct virtual environment

VS Code needs to know which Python interpreter to use for this project — otherwise
it will underline imports with red squiggles and not find packages when you run
scripts from inside VS Code.

**Step 1:** Open the project in VS Code:
```bash
code /Users/andyyaro/Downloads/multi-modal-workflow
```

**Step 2:** Open the Command Palette:
Press `Command + Shift + P`.

**Step 3:** Type and select:
```
Python: Select Interpreter
```

**Step 4:** In the list that appears, look for an option that shows the path to your
`.venv` folder:
```
Python 3.14.0 ('.venv': venv)
~/Downloads/multi-modal-workflow/.venv/bin/python
```
Click it.

**If the `.venv` interpreter does not appear in the list:**
Click **Enter interpreter path...** and type:
```
/Users/andyyaro/Downloads/multi-modal-workflow/.venv/bin/python
```
Press Enter.

**Step 5:** Verify VS Code is using the right interpreter by looking at the bottom
status bar of VS Code. You should see something like:
```
Python 3.14.0 ('.venv': venv)
```

**Step 6:** Open a new Terminal inside VS Code (`Terminal > New Terminal`). The
virtual environment should activate automatically (the prompt will show `(.venv)`).
If it does not, check that VS Code's Python extension is installed:
- Press `Command + Shift + X` to open Extensions.
- Search for `Python`.
- Install the official **Python** extension by Microsoft if not already installed.

---

## 5.11 Quick environment setup script

After the above steps work, create a helper script so you never forget the activation
command. Create the file:

```bash
code activate.sh
```

Add this content:
```bash
#!/bin/bash
# Run this from the project root to activate the virtual environment:
# source activate.sh

cd "$(dirname "${BASH_SOURCE[0]}")"
source .venv/bin/activate
echo "Virtual environment activated: $(python --version)"
echo "Ollama server check: $(curl -s http://localhost:11434 || echo 'NOT RUNNING')"
```

Save it. Make it executable:
```bash
chmod +x activate.sh
```
**What `chmod +x` does:** Gives the file execute permission so you can run it as a
script.

**How to use it (every time you start a new work session):**
```bash
source activate.sh
```
**What `source` does here:** Runs the script in the current shell session so that the
`activate` command's effect (changing your Python PATH) applies to your current
Terminal window, not a subshell.

---

*End of Sections 3, 4, and 5.*

---

> **Next sections to write:** Section 6 (Exact Models to Download) and
> Section 7 (Project Folder Setup).

---

# SECTION 6 — Model Download and Quality Profiles

## 6.0 The core quality principle

Serious local output quality comes from two things working together:

1. **Better model choices** — using capable models at realistic sizes for your hardware.
2. **A stronger review loop** — the critique-fix-judge cycle that makes any model
   produce better results than a single call.

Neither alone is enough. A great model with no loop produces one draft. A great loop
with weak models produces well-iterated mediocrity. You need both.

This section defines **four model profiles** for your M3 24GB MacBook. Each profile
is a named configuration in `config/models.yaml`. You switch between them with one
config change — no Python edits needed.

| Profile | Purpose | When to use |
|---------|---------|-------------|
| **Bootstrap** | Prove the pipeline code works | Day 1–3, debugging orchestration |
| **Serious Work** | Recommended for real outputs | Once the loop is verified working |
| **Coding Specialist** | Coding and debugging tasks | When the task is Python/code work |
| **Fast** | Quick tests, memory pressure | Testing prompt changes, low-RAM situations |

**Key principle:** The Bootstrap profile is not the final quality target.
It is a sanity-check tool. Upgrade to the Serious Work profile as soon as
the pipeline runs end-to-end without errors.

---

## 6.1 Before pulling any model

Confirm Ollama is running:
```bash
curl http://localhost:11434
```
Expected: `Ollama is running`. If not, open the Ollama app (see Section 4).

All model pulls use:
```bash
ollama pull <model-name>
```

Ollama downloads to `~/.ollama/models/` on your Mac. You only need to pull each
model once. Check available disk before pulling the Serious Work set:
```bash
df -h ~
```
The full Serious Work profile requires approximately 35–40 GB of disk space across
all models. With 1TB storage this is not a concern, but good to verify.

> **Verify tags before every pull.**
> Model tags in this guide (e.g., `qwen2.5:14b`, `phi4:14b`, `gemma3:12b`) are
> accurate as of the guide's writing but Ollama registry tags can change between
> releases. A pull with a wrong tag silently downloads a different variant or fails.
> Run `ollama search <name>` and use the exact tag from the output.
```bash
ollama search qwen2.5
ollama search phi4
ollama search gemma3
ollama search llama3.2
```
The tag in the first column of the output is what you should pass to `ollama pull`.

---

## 6.2 Bootstrap Profile — Pull This First

**Purpose:** Prove the pipeline works. Debug the orchestration loop. Tune prompt
templates. This is not where you do serious work — it is where you verify the
code is wired together correctly.

Pull one model only:
```bash
ollama pull llama3.2:3b
```

| Property | Value |
|----------|-------|
| Download size | ~2.0 GB |
| RAM when loaded | ~2.0–2.5 GB |
| Speed on M3 | Very fast — 3–10 seconds per response |
| All pipeline roles | Supervisor, Planner, Builder, Critic, Fixer, Judge, Synthesizer |
| Limitation | Output quality reflects a 3B model: adequate for testing, not for real work |
| Fallback if too slow | `llama3.2:1b` (~1 GB, ~1–3 s, lower quality) |

**Test after download:**
```bash
ollama run llama3.2:3b "In one sentence, what is the capital of France?"
```
Should respond within 10 seconds. A coherent answer confirms the model is working.

**Bootstrap pipeline call sequence:**
```
Supervisor    → llama3.2:3b   (~2 GB RAM, 3–10s)
Planner       → llama3.2:3b   (already loaded, very fast)
Builder       → llama3.2:3b   (already loaded)
Critic        → llama3.2:3b   (already loaded)
Fixer         → llama3.2:3b   (already loaded)
Judge         → llama3.2:3b   (already loaded)
Synthesizer   → llama3.2:3b   (already loaded)
```
Peak RAM: ~2.5 GB. A full 3-loop run completes in roughly 3–5 minutes.

**How to run in Bootstrap mode:**
```bash
python run.py --goal "Explain recursion." \
    --model-main llama3.2:3b \
    --model-fast llama3.2:3b \
    --max-loops 1 --threshold 40
```

**When to leave Bootstrap behind:** Once `run.py` completes without errors, all
7 agent files are saved in `runs/<timestamp>/`, and the Judge returns valid JSON —
you are done with Bootstrap. Switch to the Serious Work profile next.

---

## 6.3 Serious Work Profile — Pull This for Real Outputs

**Purpose:** The recommended default for writing, planning, study, and general tasks
once the loop is verified. Uses models from different families for Builder vs. Judge
so the system is not judging its own output with the same model that produced it.

**Why different model families matter for Judge vs. Builder:**
If the Builder and Judge are the same model (or the same model family), the Judge
tends to find the output plausible for reasons of shared training patterns — it
literally thinks in the same way. A Judge from a different family (different
architecture, different training data mix, different developer) applies a genuinely
independent critical perspective. This produces more useful scoring and harder-to-fool
pass/fail decisions.

Pull all four models:

```bash
ollama pull llama3.1:8b
ollama pull qwen2.5:14b
ollama pull gemma3:12b
ollama pull phi4:14b
```

> **Tag verification note:** Before pulling, confirm exact tags with
> `ollama search qwen2.5` and `ollama search phi4` and `ollama search gemma3`.
> Tags shown here were accurate at time of writing but Ollama registry tags
> can be updated. Use the tag exactly as shown in `ollama search` output.

---

### Model A: `llama3.1:8b` — Fast router (Supervisor + Planner)

| Property | Value |
|----------|-------|
| Download size | ~4.7 GB |
| RAM when loaded | ~4.9 GB |
| Speed on M3 | Fast — 8–20 seconds per response |
| Roles | Supervisor, Planner |
| Why this role | Routing and planning tasks are structured and shorter. A fast, capable 8B model handles them well without spending 14B model time on them. |
| Fallback | `llama3.2:3b` if speed is a priority |

```bash
ollama run llama3.1:8b "In two sentences, explain what a REST API is."
```
Should respond in 10–25 seconds with a coherent, accurate answer.

---

### Model B: `qwen2.5:14b` — Main builder (Builder + Fixer + Synthesizer)

| Property | Value |
|----------|-------|
| Download size | ~8.9 GB |
| RAM when loaded | ~8.5–9.0 GB |
| Speed on M3 | Moderate — 20–50 seconds per response |
| Roles | Builder, Fixer, Synthesizer |
| Why this role | Qwen 2.5 14B has strong instruction following, consistent output structure, and good performance across writing, planning, and explanation tasks. At 14B it noticeably outperforms 7–8B models on multi-section drafts. |
| Fallback | `llama3.1:8b` if 14B is too slow for your task cadence |

```bash
ollama run qwen2.5:14b "Write a 4-sentence explanation of how HTTPS works."
```
Should respond in 25–50 seconds. The response should be noticeably more structured
and complete than a 3B or 7B model on the same prompt.

---

### Model C: `gemma3:12b` — Critic (independent lineage)

| Property | Value |
|----------|-------|
| Download size | ~7.7 GB |
| RAM when loaded | ~7.3–8.0 GB |
| Speed on M3 | Moderate — 15–40 seconds per response |
| Roles | Critic |
| Why this role | Google's Gemma 3 12B uses a different architecture and training approach from both Qwen and Phi. Using it specifically for critique means the Critic evaluates the Builder's output from a genuinely different perspective. |
| Fallback | `llama3.1:8b` if you want to reduce the model count |

```bash
ollama run gemma3:12b "What is one weakness in this sentence: 'The project was completed by the team in a timely manner.'"
```
Should respond in 15–40 seconds with a specific, useful critique.

---

### Model D: `phi4:14b` — Judge (strong reasoning, different family)

| Property | Value |
|----------|-------|
| Download size | ~8.9 GB |
| RAM when loaded | ~8.5–9.0 GB |
| Speed on M3 | Moderate — 20–50 seconds per response |
| Roles | Judge |
| Why this role | Microsoft's Phi-4 14B is known for structured reasoning and strict instruction following — both critical for JSON schema compliance. It is from a different model family than both Qwen (Builder) and Gemma (Critic), providing genuinely independent scoring. |
| Fallback | `gemma3:12b` doubles as Judge if you want to pull one fewer model |

**Test JSON compliance (required for the Judge role):**
```bash
ollama run phi4:14b 'Return ONLY valid JSON, nothing else: {"score": 82, "pass": true}'
```
The response must start with `{` and end with `}` with no surrounding text.
If it adds explanation, the Judge prompt in Section 17 handles it with retry logic.

---

### Serious Work profile summary

```
Supervisor    → llama3.1:8b   (~4.9 GB RAM, 8–20s)
Planner       → llama3.1:8b   (already loaded, fast)
Builder       → qwen2.5:14b   (~8.5 GB RAM, 20–50s)
Critic        → gemma3:12b    (~7.5 GB RAM, 15–40s)
Fixer         → qwen2.5:14b   (reloads if unloaded, 20–50s)
Judge         → phi4:14b      (~8.5 GB RAM, 20–50s)
Synthesizer   → qwen2.5:14b   (reloads if unloaded)
```

Peak RAM at any point: ~9 GB (one 14B model loaded). Headroom: ~11 GB.
Estimated time per loop iteration: 90–180 seconds. A 3-loop run: 5–9 minutes.

**How to run in Serious Work mode:**
```bash
python run.py --goal "Your goal here" \
    --model-main qwen2.5:14b \
    --model-fast llama3.1:8b \
    --max-loops 3 --threshold 70
```

Or set it permanently in `config/models.yaml` (see Section 18).

---

## 6.4 Coding Specialist Profile — Pull for Code Tasks

**Purpose:** When the primary task is writing Python code, a coding-specialized
Builder/Fixer significantly outperforms a general-purpose model of similar size.

Pull one additional model beyond the Serious Work set:
```bash
ollama pull qwen2.5-coder:14b
```

> **Tag verification:** Run `ollama search qwen2.5-coder` to confirm the exact tag.

| Property | Value |
|----------|-------|
| Download size | ~8.9 GB |
| RAM when loaded | ~8.5–9.0 GB |
| Speed on M3 | Moderate — 20–50 seconds per response |
| Roles | Builder, Fixer in Coding and Debugging modes |
| Why this role | Qwen 2.5 Coder 14B is trained specifically on code generation and is a better choice for Python tasks than the general Qwen 2.5 14B. Uses the same base architecture so the behavioral profile is familiar. |
| Fallback | `qwen2.5-coder:7b` (~4.7 GB, ~5 GB RAM, faster but lower quality) |

```bash
ollama run qwen2.5-coder:14b "Write a Python function that removes duplicate values from a list while preserving order."
```
Should produce syntactically correct Python with a clear function signature and
an example usage block.

**Coding Specialist pipeline:**
```
Supervisor    → llama3.1:8b        (~4.9 GB RAM)
Planner       → llama3.1:8b        (already loaded)
Builder       → qwen2.5-coder:14b  (~8.5 GB RAM)  ← coding specialist
Critic        → gemma3:12b         (~7.5 GB RAM)
Fixer         → qwen2.5-coder:14b  (reloads)       ← coding specialist
Judge         → phi4:14b           (~8.5 GB RAM)
Synthesizer   → qwen2.5:14b        (~8.5 GB RAM)
```

**How to activate in config** (see Section 18 for full setup):
```yaml
# config/models.yaml — coding profile active
mode_overrides:
  coding:
    builder: "qwen2.5-coder:14b"
    fixer:   "qwen2.5-coder:14b"
  debugging:
    builder: "qwen2.5-coder:14b"
    fixer:   "qwen2.5-coder:14b"
```

**Disk budget for full Coding Specialist set:**
`llama3.2:3b` + `llama3.1:8b` + `qwen2.5:14b` + `qwen2.5-coder:14b` +
`gemma3:12b` + `phi4:14b` ≈ **40–42 GB total**. Trivial on 1TB storage.

---

## 6.5 Fast / Low-Memory Profile — For Testing and Tight RAM

**Purpose:** Quick prompt iteration, testing code changes, or running when other
applications are consuming RAM. Explicitly lower quality than the Serious Work
profile. Use this to check if a prompt change works, not to produce final output.

No additional pulls needed if you have `llama3.2:3b` and `llama3.1:8b` already.

```
Supervisor    → llama3.2:3b   (~2 GB RAM, 3–10s)
Planner       → llama3.2:3b   (already loaded)
Builder       → llama3.1:8b   (~4.9 GB RAM, 8–20s)
Critic        → llama3.2:3b   (reloads small model)
Fixer         → llama3.1:8b   (reloads)
Judge         → llama3.1:8b   (already loaded)
Synthesizer   → llama3.1:8b   (already loaded)
```

Peak RAM: ~5 GB. A 3-loop run completes in roughly 3–6 minutes.

**How to run in Fast mode:**
```bash
python run.py --goal "Your goal here" \
    --model-main llama3.1:8b \
    --model-fast llama3.2:3b \
    --max-loops 2 --threshold 55
```

---

## 6.6 Future API Profile — Disabled by Default

No models to pull. The architecture supports adding OpenAI or Anthropic as
providers later via `config/models.yaml` without touching Python code.
This is covered in Section 18. Do not configure it now.

---

## 6.7 Recommended pull sequence

Pull in this order. Stop after Step 1 for Day 1. Continue to Step 2 after
the pipeline loop is verified end-to-end.

**Step 1 — Bootstrap (Day 1, ~2 GB):**
```bash
ollama pull llama3.2:3b
```

**Step 2 — Serious Work router (Day 3–4, ~4.7 GB more):**
```bash
ollama pull llama3.1:8b
```

**Step 3 — Serious Work builder (Day 4, ~8.9 GB more):**
```bash
ollama pull qwen2.5:14b
```

**Step 4 — Serious Work critic (Day 4, ~7.7 GB more):**
```bash
ollama pull gemma3:12b
```

**Step 5 — Serious Work judge (Day 4, ~8.9 GB more):**
```bash
ollama pull phi4:14b
```

**Step 6 — Coding specialist, optional (Day 5+, ~8.9 GB more):**
```bash
ollama pull qwen2.5-coder:14b
```

---

## 6.8 How to benchmark models for your own tasks

Before committing to a profile for a specific type of work, run a direct comparison:

```bash
# Test writing quality — same prompt, different models
ollama run llama3.2:3b "Write a 4-sentence explanation of neural networks for a software developer."
ollama run llama3.1:8b "Write a 4-sentence explanation of neural networks for a software developer."
ollama run qwen2.5:14b "Write a 4-sentence explanation of neural networks for a software developer."
```

Evaluate the output yourself on:
- **Specificity:** Does it say something concrete or stay vague?
- **Accuracy:** Is what it says actually correct?
- **Structure:** Is it easy to read?
- **Completeness:** Does it address the prompt fully?

```bash
# Test JSON reliability — critical for the Judge role
ollama run llama3.1:8b 'Return ONLY valid JSON: {"score": 74, "pass": true, "rationale": "Good."}'
ollama run phi4:14b    'Return ONLY valid JSON: {"score": 74, "pass": true, "rationale": "Good."}'
```

The model that returns clean JSON more consistently is the better Judge candidate
on your specific hardware and Ollama version.

```bash
# Test coding quality
ollama run llama3.1:8b "Write a Python function that parses a date string in YYYY-MM-DD format and returns year, month, day as a tuple."
ollama run qwen2.5-coder:14b "Write a Python function that parses a date string in YYYY-MM-DD format and returns year, month, day as a tuple."
```

The output that is syntactically valid, handles edge cases, and includes a
usage example is the better coding model for your purposes.

---

## 6.9 When to switch profiles

| Situation | Use profile |
|-----------|-------------|
| First run ever, verifying the pipeline works | Bootstrap |
| Debugging a Python error in orchestration code | Bootstrap |
| Tuning a prompt template (quick iteration) | Fast |
| Writing a blog post, explanation, or guide | Serious Work |
| Creating a project plan or decision framework | Serious Work |
| Writing new Python code or debugging existing code | Coding Specialist |
| Mac is running hot or memory pressure is yellow | Fast |
| Showing the system to someone for the first time | Serious Work |
| Running overnight with max loops | Serious Work |

---

## 6.10 How to list all downloaded models

```bash
ollama list
```
**Example output after pulling the Serious Work set:**
```
NAME                    ID              SIZE      MODIFIED
llama3.2:3b             a80c4f17acd5    2.0 GB    5 days ago
llama3.1:8b             42182419e950    4.7 GB    2 days ago
qwen2.5:14b             ad2b1e95c7bf    8.9 GB    1 day ago
gemma3:12b              f5b76b3c5b60    7.7 GB    1 day ago
phi4:14b                4c52e786a9a1    8.9 GB    1 day ago
qwen2.5-coder:14b       8a8d5fe4a6df    8.9 GB    10 hours ago
```
(IDs and sizes are illustrative — your actual values will differ.)

---

## 6.11 How to check total disk usage for Ollama models

```bash
du -sh ~/.ollama/models/
```

---

## 6.12 How to test any model after downloading

```bash
ollama run <model-name> "Respond with exactly one word: the color of the sky."
```
If no response within 90 seconds, press `Control + C`. Check memory pressure.

Test JSON compliance (critical for any model used as Judge):
```bash
ollama run <model-name> 'Return ONLY valid JSON, nothing else: {"score": 80, "pass": true}'
```
The first character of the response must be `{`. If the model adds surrounding
text, the Judge prompt retry logic handles it (Section 17), but a model that
returns clean JSON on this test will be more reliable in practice.

---

## 6.13 How to remove a model

⚠️ **Warning:** This permanently removes the model file from disk.
You must re-download it to use it again.

```bash
ollama rm <model-name>
```
Verify it is gone:
```bash
ollama list
```

---

# SECTION 7 — Project Folder Setup

## 7.1 The project root

Your project already lives at:
```
/Users/andyyaro/Downloads/multi-modal-workflow/
```

You will build everything inside this folder. All commands in this section assume
you are already in the project root. If you are not, run:
```bash
cd ~/Downloads/multi-modal-workflow
```

**Why `~/Downloads/`?** It is already there and it works fine for development.
Later you can move the folder to `~/Projects/` or anywhere you prefer — just update
your VS Code workspace and Git remote URL accordingly. Nothing in the code uses
absolute paths except what you configure in Section 18.

---

## 7.2 MVP folder structure (what to create today)

For the terminal MVP, you only need a subset of the full folder tree. Create only
what is listed below. Add the rest when you reach the phase that needs them.

**What to create for the MVP:**
```
multi-modal-workflow/
├── .venv/                  ← already created in Section 5
├── agents/                 ← one Python file per agent role
├── config/                 ← YAML config for models and modes
├── prompts/                ← prompt template text files
├── runs/                   ← auto-created at runtime; holds output files
├── logs/                   ← log files for debugging
├── tests/                  ← test scripts
├── run.py                  ← main entry point
├── requirements.txt        ← already created in Section 5
├── requirements-lock.txt   ← generated after pip freeze
├── activate.sh             ← already created in Section 5
├── .gitignore              ← what NOT to commit to GitHub
└── LOCAL_AI_ORCHESTRATOR_BUILD_GUIDE.md  ← this file
```

**What to add later (not now):**
```
├── app/                    ← Streamlit app (Phase 6)
├── orchestrator/           ← LangGraph graph definition (Phase 5)
└── outputs/                ← polished final outputs (Phase 6+)
```

---

## 7.3 Create all MVP folders and files

Make sure you are in the project root first:
```bash
pwd
```
Expected: `/Users/andyyaro/Downloads/multi-modal-workflow`

Create all subdirectories:
```bash
mkdir -p agents config prompts runs logs tests
```
**What `mkdir -p` does:** Creates directories. The `-p` flag means "create any
missing parent directories and do not error if the directory already exists." You can
run this safely multiple times.

Verify the folders were created:
```bash
ls -la
```

**Expected output:**
```
drwxr-xr-x   agents/
drwxr-xr-x   config/
-rw-r--r--   LOCAL_AI_ORCHESTRATOR_BUILD_GUIDE.md
drwxr-xr-x   logs/
drwxr-xr-x   prompts/
-rw-r--r--   requirements.txt
drwxr-xr-x   runs/
drwxr-xr-x   tests/
drwxr-xr-x   .venv/
```

---

## 7.4 Create placeholder `__init__.py` files

Python needs `__init__.py` files inside folders to treat them as importable packages.
Create empty ones now:

```bash
touch agents/__init__.py
touch tests/__init__.py
```
**What `touch` does:** Creates an empty file if it does not exist, or updates its
modification timestamp if it does. The `__init__.py` files can be empty — their
presence is what matters.

You do not need `__init__.py` in `config/`, `prompts/`, `runs/`, or `logs/` because
those folders hold data files, not Python modules.

---

## 7.5 Create the main entry point

```bash
touch run.py
```

Leave this file empty for now. You will fill it in Section 8. Its purpose is to be
the single command you run to start the pipeline:
```bash
python run.py --goal "your goal here"
```

---

## 7.6 Create the agent skeleton files

```bash
touch agents/base_agent.py
touch agents/supervisor.py
touch agents/planner.py
touch agents/builder.py
touch agents/critic.py
touch agents/fixer.py
touch agents/judge.py
touch agents/synthesizer.py
```

**What each file will contain:**
- `base_agent.py` — shared logic: how to call Ollama, handle errors, retry.
- `supervisor.py` — the Supervisor agent class.
- `planner.py` — the Planner agent class.
- `builder.py` — the Builder agent class.
- `critic.py` — the Critic agent class.
- `fixer.py` — the Fixer agent class.
- `judge.py` — the Judge agent class (returns JSON scores).
- `synthesizer.py` — the Final Synthesizer agent class.

You will fill these in during Phases 2–4 (Sections 9–11).

---

## 7.7 Create the config skeleton files

```bash
touch config/models.yaml
touch config/modes.yaml
```

Leave these empty for now. You will fill them in Section 18. Their purpose:
- `models.yaml` — maps each agent role to a specific model name.
- `modes.yaml` — defines Writing, Coding, Planning, Debugging, and Study modes.

---

## 7.8 Create the prompt template files

```bash
touch prompts/supervisor.txt
touch prompts/planner.txt
touch prompts/builder.txt
touch prompts/critic.txt
touch prompts/fixer.txt
touch prompts/judge.txt
touch prompts/synthesizer.txt
```

These will hold the system prompt templates for each agent. Keeping prompts in
separate text files (rather than hardcoded in Python) makes them easy to edit without
touching code. You will fill these in Section 17.

---

## 7.9 Create the `.gitignore` file

⚠️ **Create this before your first Git commit.** The `.gitignore` file tells Git
which files and folders to never track. Missing this step means you could accidentally
commit your virtual environment (thousands of files) or sensitive data to GitHub.

```bash
touch .gitignore
code .gitignore
```

Add this content exactly:
```
# Virtual environment — never commit this
.venv/

# Python cache files — auto-generated, not needed in version control
__pycache__/
*.pyc
*.pyo
*.pyd
.Python

# Run output files — these are generated data, not source code
runs/
logs/

# SQLite database file (contains your run history — keep locally)
*.db
*.sqlite3

# macOS system files
.DS_Store
.AppleDouble
.LSOverride

# VS Code settings (optional — some teams commit this, some do not)
.vscode/

# Environment variable files (never commit these — they may contain secrets)
.env
.env.local
.env.*

# Pip wheel cache
*.egg-info/
dist/
build/

# pytest cache
.pytest_cache/

# Jupyter notebooks checkpoints (if you ever use them)
.ipynb_checkpoints/
```

Save the file.

**Note about `runs/` and `logs/`:** You are excluding these because they will
contain generated output text, which can be large and is not source code. If you
want to commit a specific example run for your portfolio, you can manually stage
that file with `git add runs/example-run/` even though `runs/` is in `.gitignore`.

---

## 7.10 Create a `logs/` placeholder

The `runs/` and `logs/` folders are excluded from Git, but they need to exist
locally for the app to write to them. Git does not track empty folders. Create a
`.gitkeep` placeholder in each so the folders persist in Git:

```bash
touch logs/.gitkeep
touch runs/.gitkeep
```

**What `.gitkeep` is:** An empty file with a conventional name that tells other
developers "this empty folder is intentional and should exist." Git tracks this file,
which forces it to track the folder.

Update your `.gitignore` to ignore everything in `runs/` and `logs/` EXCEPT the
placeholder files. Open `.gitignore` in VS Code and replace:
```
runs/
logs/
```
with:
```
# Ignore generated run and log content but keep the folders tracked
runs/*
!runs/.gitkeep
logs/*
!logs/.gitkeep
```

**What `!` means in `.gitignore`:** The `!` prefix means "do NOT ignore this
pattern, even if a previous rule would ignore it." So `runs/*` ignores all files
inside `runs/`, but `!runs/.gitkeep` overrides that for `.gitkeep` specifically.

---

## 7.11 Create a minimal `config/models.yaml`

```bash
code config/models.yaml
```

Add this content. It uses the **Bootstrap profile** for your first run.
You will upgrade this to the Serious Work profile in Section 18 after the
pipeline is verified end-to-end.

```yaml
# Model assignments for each agent role.
# Change these values to swap models without editing Python code.
# See Section 18 for the full profile-switching configuration.

provider: ollama
base_url: "http://localhost:11434"

# ACTIVE PROFILE: bootstrap
# Switch to "serious", "coding", or "fast" after the loop is verified.
active_profile: bootstrap

profiles:
  bootstrap:
    supervisor:  "llama3.2:3b"
    planner:     "llama3.2:3b"
    builder:     "llama3.2:3b"
    critic:      "llama3.2:3b"
    fixer:       "llama3.2:3b"
    judge:       "llama3.2:3b"
    synthesizer: "llama3.2:3b"

  serious:
    supervisor:  "llama3.1:8b"
    planner:     "llama3.1:8b"
    builder:     "qwen2.5:14b"
    critic:      "gemma3:12b"
    fixer:       "qwen2.5:14b"
    judge:       "phi4:14b"
    synthesizer: "qwen2.5:14b"

defaults:
  temperature: 0.7
  num_ctx: 4096

memory:
  keep_alive: "5m"
```

Save the file.

---

## 7.12 Open the full project in VS Code

```bash
code /Users/andyyaro/Downloads/multi-modal-workflow
```

VS Code will open with the project folder in the Explorer panel on the left. You
should see all the folders and files you just created.

**Set the Python interpreter** (if you have not already — see Section 5.10):
- Press `Command + Shift + P`
- Type `Python: Select Interpreter`
- Select the `.venv` interpreter

---

## 7.13 Final folder structure verification

Run this to confirm everything is in place:
```bash
find . -not -path './.venv/*' -not -path './__pycache__/*' | sort
```
**What this does:** Lists every file and folder in the project directory, excluding
the `.venv` folder (which has thousands of files) and `__pycache__`. The `sort` at
the end alphabetizes the output for easy reading.

**Expected output:**
```
.
./.gitignore
./LOCAL_AI_ORCHESTRATOR_BUILD_GUIDE.md
./activate.sh
./agents
./agents/__init__.py
./agents/base_agent.py
./agents/builder.py
./agents/critic.py
./agents/fixer.py
./agents/judge.py
./agents/planner.py
./agents/supervisor.py
./agents/synthesizer.py
./config
./config/models.yaml
./config/modes.yaml
./logs
./logs/.gitkeep
./prompts
./prompts/builder.txt
./prompts/critic.txt
./prompts/fixer.txt
./prompts/judge.txt
./prompts/planner.txt
./prompts/supervisor.txt
./prompts/synthesizer.txt
./requirements.txt
./run.py
./runs
./runs/.gitkeep
./tests
./tests/__init__.py
```

If any file or folder is missing, create it now using `touch <path>` or `mkdir <path>`
before moving on. The pipeline code in later sections assumes this exact structure.

---

*End of Sections 6 and 7.*

---

> **Next sections to write:** Section 8 (Phase 1 — First Local Model Call) and
> Section 9 (Phase 2 — Builder → Critic Terminal Loop).

---

# SECTION 8 — Phase 1: First Local Model Call

This is the simplest possible test. One Python file, one prompt, one model call,
one printed response. Before building the full pipeline, you need to confirm that
Python can talk to Ollama successfully on your machine.

---

## 8.1 Verify Ollama is running before you start

Always check this first:
```bash
curl http://localhost:11434
```
Expected: `Ollama is running`

Also confirm the model you are about to use is downloaded:
```bash
ollama list
```
You should see `llama3.2:3b` in the list. If not, pull it:
```bash
ollama pull llama3.2:3b
```

---

## 8.2 The test file

**File path:** `/Users/andyyaro/Downloads/multi-modal-workflow/test_ollama.py`

Create it:
```bash
code test_ollama.py
```

Add this exact content:

```python
"""
test_ollama.py

Simplest possible test: send one prompt to a local Ollama model and print
the response. Run this to confirm Python can communicate with Ollama before
building the full pipeline.

Usage:
    python test_ollama.py
"""

import requests
import json
import sys


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:3b"
PROMPT = "In exactly two sentences, explain what a neural network is."


def call_ollama(model: str, prompt: str, url: str = OLLAMA_URL) -> str:
    """Send a prompt to Ollama and return the complete response text."""

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }

    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        print("\n[ERROR] Could not connect to Ollama.")
        print("  Make sure Ollama is running: open the Ollama app or run 'ollama serve'")
        print("  Then verify with: curl http://localhost:11434")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print("\n[ERROR] Request timed out after 120 seconds.")
        print("  The model may be too large or your Mac is under memory pressure.")
        print("  Try: ollama run llama3.2:3b 'hello' in Terminal to test directly.")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"\n[ERROR] HTTP error from Ollama: {e}")
        print(f"  Status code: {response.status_code}")
        print(f"  Response body: {response.text[:500]}")
        sys.exit(1)

    data = response.json()
    return data.get("response", "").strip()


def main():
    print(f"Model  : {MODEL}")
    print(f"Prompt : {PROMPT}")
    print("-" * 60)
    print("Calling Ollama... (may take 10–30 seconds on first load)")
    print()

    result = call_ollama(MODEL, PROMPT)

    print("Response:")
    print(result)
    print()
    print("[SUCCESS] Ollama is working correctly.")


if __name__ == "__main__":
    main()
```

Save the file.

---

## 8.3 Run the test

Make sure your virtual environment is active (you should see `(.venv)` in your
prompt). If not:
```bash
source .venv/bin/activate
```

Run the script:
```bash
python test_ollama.py
```

**What this does:** Sends a POST request to the Ollama HTTP API at
`http://localhost:11434/api/generate` with the model name and your prompt. Ollama
loads the model (if not already in memory), runs inference, and returns JSON
containing the response text. The script extracts that text and prints it.

---

## 8.4 Expected output

```
Model  : llama3.2:3b
Prompt : In exactly two sentences, explain what a neural network is.
------------------------------------------------------------
Calling Ollama... (may take 10–30 seconds on first load)

Response:
A neural network is a computational model inspired by the human brain,
consisting of layers of interconnected nodes that process and transform input
data. It learns patterns by adjusting the strength of connections between
nodes during a training process guided by example data.

[SUCCESS] Ollama is working correctly.
```

The exact wording of the response will vary — model outputs are not deterministic.
What matters: a non-empty, coherent response appears, and the script exits without
errors.

**First-run timing:** If `llama3.2:3b` is not yet in Ollama's memory, it loads from
disk first. On an M3 with an SSD, this takes 3–8 seconds. The actual inference then
takes another 5–15 seconds. Total: 8–30 seconds for the first call. Subsequent calls
to the same model in the same session are much faster.

---

## 8.5 What to do if you get a connection error

**Symptom:**
```
[ERROR] Could not connect to Ollama.
```

**Fix — Step 1:** Check if Ollama is running:
```bash
curl http://localhost:11434
```
If this returns `Ollama is running`, the connection works and the Python error was
transient. Run the script again.

**Fix — Step 2:** If `curl` also fails, start Ollama:
```bash
open -a Ollama
# wait 5 seconds
curl http://localhost:11434
```

**Fix — Step 3:** If Ollama is running but the Python script still cannot connect,
check that you are calling the right URL. The default port is `11434`. If you changed
it (Section 4.8), update `OLLAMA_URL` in the script accordingly.

---

## 8.6 What to do if the model is not found

**Symptom:** The script exits with an HTTP error, and the Ollama server log (if you
are running `ollama serve` in a Terminal window) shows:
```
model 'llama3.2:3b' not found
```

**Fix:** Pull the model:
```bash
ollama pull llama3.2:3b
```
After the download completes, run the script again.

**If you want to use a different model** (because `llama3.2:3b` is too slow or
unavailable), change the `MODEL` variable at the top of `test_ollama.py`:
```python
MODEL = "llama3.2:1b"   # smaller, faster fallback
```

---

## 8.7 What to do if the response is very slow

If the script runs for more than 90 seconds without printing anything:

1. Press `Control + C` to cancel.
2. Open Activity Monitor and check the Memory tab. Is Memory Pressure yellow or red?
3. Close other applications to free RAM.
4. Try the smaller model:
   ```bash
   $ ollama pull llama3.2:1b
   ```
   Then change `MODEL = "llama3.2:1b"` in the script and run again.
5. If it is still slow, restart Ollama:
   ```bash
   $ pkill -f "ollama" && sleep 2 && open -a Ollama
   ```

---

## 8.8 What success looks like

You have passed Phase 1 when:
- [ ] `python test_ollama.py` runs without errors.
- [ ] A non-empty, coherent response is printed.
- [ ] The script prints `[SUCCESS] Ollama is working correctly.`
- [ ] The whole run (including model load) takes under 60 seconds.

Keep `test_ollama.py` in your project. You will reuse the `call_ollama()` function
as the foundation for the `base_agent.py` in the next section.

---

# SECTION 9 — Phase 2: Two-Agent Builder → Critic Terminal Loop

Now you build the first real two-agent workflow. The Builder writes a draft. The
Critic reviews it. Both outputs are saved to files. This is still terminal-only.

---

## 9.1 Write `agents/base_agent.py`

This file contains the shared logic that all agents use: how to call Ollama, how to
load a prompt template, and how to handle errors. Every agent inherits from this.

**File path:** `agents/base_agent.py`

Open it:
```bash
code agents/base_agent.py
```

Add this content:

```python
"""
agents/base_agent.py

Base class for all pipeline agents. Provides shared Ollama call logic,
prompt template loading, and error handling. All agent classes inherit from
BaseAgent and override the `run()` method.
"""

import requests
import json
import time
import sys
from pathlib import Path


OLLAMA_URL = "http://localhost:11434/api/generate"
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class BaseAgent:
    """
    Shared foundation for all pipeline agents.

    Subclasses must set self.role and self.model, then implement run().
    """

    def __init__(self, model: str, role: str, temperature: float = 0.7,
                 num_ctx: int = 4096, max_retries: int = 2):
        self.model = model
        self.role = role
        self.temperature = temperature
        self.num_ctx = num_ctx
        self.max_retries = max_retries

    def load_prompt_template(self) -> str:
        """Load the prompt template for this agent from prompts/<role>.txt."""
        template_path = PROMPTS_DIR / f"{self.role}.txt"
        if not template_path.exists():
            raise FileNotFoundError(
                f"Prompt template not found: {template_path}\n"
                f"Create the file prompts/{self.role}.txt with your system prompt."
            )
        return template_path.read_text(encoding="utf-8").strip()

    def call_model(self, prompt: str) -> str:
        """
        Send a prompt to Ollama and return the response text.
        Retries up to self.max_retries times on transient errors.
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.num_ctx,
            },
        }

        for attempt in range(1, self.max_retries + 2):
            try:
                response = requests.post(
                    OLLAMA_URL, json=payload, timeout=180
                )
                response.raise_for_status()
                data = response.json()
                text = data.get("response", "").strip()
                if not text:
                    raise ValueError("Ollama returned an empty response.")
                return text

            except requests.exceptions.ConnectionError:
                self._fatal(
                    "Cannot connect to Ollama at http://localhost:11434\n"
                    "Start Ollama: open -a Ollama"
                )

            except requests.exceptions.Timeout:
                if attempt <= self.max_retries:
                    print(f"  [WARN] Timeout on attempt {attempt}, retrying...")
                    time.sleep(3)
                    continue
                self._fatal(
                    f"Request timed out after {self.max_retries + 1} attempts.\n"
                    "Try a smaller model or check memory pressure."
                )

            except (requests.exceptions.HTTPError, ValueError) as e:
                if attempt <= self.max_retries:
                    print(f"  [WARN] Error on attempt {attempt}: {e}. Retrying...")
                    time.sleep(3)
                    continue
                self._fatal(str(e))

        self._fatal("All retry attempts failed.")

    def _fatal(self, message: str):
        """Print an error message and exit."""
        print(f"\n[ERROR] Agent '{self.role}' failed: {message}")
        sys.exit(1)

    def run(self, **kwargs) -> str:
        """Override in subclasses. Returns the agent's output as a string."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement run()")
```

Save the file.

---

## 9.2 Write the Builder agent

**File path:** `agents/builder.py`

```bash
code agents/builder.py
```

```python
"""
agents/builder.py

The Builder agent creates the first draft of the deliverable.
It receives the goal and the planner's outline, and produces a full draft.
"""

from agents.base_agent import BaseAgent


class BuilderAgent(BaseAgent):

    def __init__(self, model: str, **kwargs):
        super().__init__(model=model, role="builder", **kwargs)

    def run(self, goal: str, plan: str) -> str:
        """
        Build a first draft based on the goal and plan.

        Args:
            goal: The user's original goal statement.
            plan: The structured plan from the Planner agent.

        Returns:
            The full text of the first draft.
        """
        system_prompt = self.load_prompt_template()

        full_prompt = f"""{system_prompt}

USER GOAL:
{goal}

PLAN TO FOLLOW:
{plan}

Now write the complete deliverable according to the plan above.
"""
        print(f"  [Builder] Calling {self.model}...")
        result = self.call_model(full_prompt)
        print(f"  [Builder] Draft complete ({len(result)} chars)")
        return result
```

Save the file.

---

## 9.3 Write the Critic agent

**File path:** `agents/critic.py`

```bash
code agents/critic.py
```

```python
"""
agents/critic.py

The Critic agent reviews a draft against the original goal and produces
structured, actionable feedback. It does not rewrite — only critiques.
"""

from agents.base_agent import BaseAgent


class CriticAgent(BaseAgent):

    def __init__(self, model: str, **kwargs):
        super().__init__(model=model, role="critic", **kwargs)

    def run(self, goal: str, draft: str) -> str:
        """
        Critique the draft against the original goal.

        Args:
            goal: The user's original goal statement.
            draft: The draft text produced by the Builder.

        Returns:
            A structured critique as plain text.
        """
        system_prompt = self.load_prompt_template()

        full_prompt = f"""{system_prompt}

ORIGINAL GOAL:
{goal}

DRAFT TO REVIEW:
{draft}

Provide your critique now. Be specific and actionable.
"""
        print(f"  [Critic] Calling {self.model}...")
        result = self.call_model(full_prompt)
        print(f"  [Critic] Critique complete ({len(result)} chars)")
        return result
```

Save the file.

---

## 9.4 Write the prompt templates

**File path:** `prompts/builder.txt`

```bash
code prompts/builder.txt
```

```
You are an expert Builder agent in a multi-agent quality improvement system.

Your job is to produce a high-quality first draft of the requested deliverable.
You will be given a user goal and a structured plan. Follow the plan closely
but use your full expertise to make each section thorough and well-written.

Rules:
- Write the complete deliverable, not a summary or outline.
- Follow the plan structure but expand each point into full prose (or code, if coding).
- Do not mention that you are an AI.
- Do not apologize, hedge, or add caveats about your limitations.
- Do not include meta-commentary like "here is my draft" or "I hope this helps."
- Just produce the actual deliverable, ready to be reviewed.
```

Save the file.

---

**File path:** `prompts/critic.txt`

```bash
code prompts/critic.txt
```

```
You are an expert Critic agent in a multi-agent quality improvement system.

Your job is to review a draft against the original goal and identify specific,
actionable weaknesses. You are rigorous but fair. Your criticism must be
specific — not vague.

Rules:
- Read the original goal carefully before evaluating the draft.
- Identify every significant weakness: missing content, logical gaps, unclear
  writing, structural problems, factual errors, incomplete sections, poor examples.
- For each weakness, explain exactly what is wrong and what should be done to fix it.
- If the draft is genuinely good in a specific area, say so briefly.
- Do not rewrite the draft. Only critique it.
- Do not be vague. "The introduction is weak" is not useful. "The introduction
  does not state the main argument and jumps immediately to details without context"
  is useful.
- Format your critique as a numbered list of specific issues, each with:
    Issue: [what is wrong]
    Location: [where in the draft]
    Fix: [what should be done]
- End with a one-sentence overall assessment.
```

Save the file.

---

## 9.5 Write the two-agent pipeline script

This is the first real pipeline. It calls Builder then Critic, saves both outputs,
and prints a clean summary.

**File path:** `run_phase2.py`

```bash
code run_phase2.py
```

```python
"""
run_phase2.py

Phase 2: Two-agent terminal pipeline.
Builder writes a draft. Critic reviews it.
Outputs are saved to runs/<timestamp>/.

Usage:
    python run_phase2.py --goal "Your goal here"
    python run_phase2.py --goal "Your goal here" --model llama3.2:3b
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from agents.builder import BuilderAgent
from agents.critic import CriticAgent


DEFAULT_MODEL_FAST = "llama3.2:3b"
DEFAULT_MODEL_MAIN = "llama3.2:3b"   # Bootstrap default — upgrade via config/models.yaml
RUNS_DIR = Path("runs")


def make_run_dir() -> Path:
    """Create a timestamped directory for this run's output files."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RUNS_DIR / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def save_file(run_dir: Path, filename: str, content: str):
    """Write content to a file inside the run directory."""
    filepath = run_dir / filename
    filepath.write_text(content, encoding="utf-8")
    print(f"  [Saved] {filepath}")


def print_separator(label: str):
    width = 60
    print()
    print("=" * width)
    print(f"  {label}")
    print("=" * width)


def main():
    parser = argparse.ArgumentParser(
        description="Phase 2: Builder → Critic terminal pipeline"
    )
    parser.add_argument(
        "--goal", required=True,
        help="The goal or task you want the pipeline to work on."
    )
    parser.add_argument(
        "--model-main", default=DEFAULT_MODEL_MAIN,
        help=f"Model for Builder (default: {DEFAULT_MODEL_MAIN})"
    )
    parser.add_argument(
        "--model-fast", default=DEFAULT_MODEL_FAST,
        help=f"Model for Critic (default: {DEFAULT_MODEL_FAST})"
    )
    args = parser.parse_args()

    goal = args.goal.strip()
    run_dir = make_run_dir()

    print()
    print("LOCAL AI ORCHESTRATOR — Phase 2: Builder → Critic")
    print(f"Run directory : {run_dir}")
    print(f"Goal          : {goal}")
    print(f"Builder model : {args.model_main}")
    print(f"Critic model  : {args.model_fast}")

    # ── STEP 1: BUILDER ──────────────────────────────────────────────────────
    print_separator("STEP 1 of 2: BUILDER")
    print("  The Builder will write a full draft based on your goal.")
    print()

    # For Phase 2, pass the goal directly as the plan (no Planner yet)
    plan_stub = f"Write a thorough, well-structured response to this goal:\n{goal}"

    builder = BuilderAgent(model=args.model_main)
    draft = builder.run(goal=goal, plan=plan_stub)

    save_file(run_dir, "01_builder_draft.txt", draft)

    print()
    print("BUILDER OUTPUT:")
    print("-" * 60)
    print(draft)

    # ── STEP 2: CRITIC ───────────────────────────────────────────────────────
    print_separator("STEP 2 of 2: CRITIC")
    print("  The Critic will review the draft against your original goal.")
    print()

    critic = CriticAgent(model=args.model_fast)
    critique = critic.run(goal=goal, draft=draft)

    save_file(run_dir, "02_critic_review.txt", critique)

    # Save run metadata
    metadata = {
        "goal": goal,
        "builder_model": args.model_main,
        "critic_model": args.model_fast,
        "run_dir": str(run_dir),
        "draft_length": len(draft),
        "critique_length": len(critique),
    }
    save_file(run_dir, "metadata.json", json.dumps(metadata, indent=2))

    print()
    print("CRITIC OUTPUT:")
    print("-" * 60)
    print(critique)

    # ── SUMMARY ──────────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  RUN COMPLETE")
    print("=" * 60)
    print(f"  Run saved to : {run_dir}/")
    print(f"  Files saved  :")
    print(f"    01_builder_draft.txt  ({len(draft)} chars)")
    print(f"    02_critic_review.txt  ({len(critique)} chars)")
    print(f"    metadata.json")
    print()
    print("  Next step: Review the critique in the run directory.")
    print("  If the critique is useful, proceed to Phase 3 (Fixer + Judge).")


if __name__ == "__main__":
    main()
```

Save the file.

---

## 9.6 Run the two-agent pipeline

Make sure your virtual environment is active and Ollama is running.

```bash
python run_phase2.py --goal "Write a short explanation of how transformers work in machine learning, suitable for a developer who knows Python but has not studied ML."
```

**What to expect:**
1. The Builder calls `llama3.2:3b` (Bootstrap default) and writes a draft (~5–15 seconds).
2. The Critic calls `llama3.2:3b` and reviews the draft (~5–15 seconds).
3. Both outputs print to the terminal.
4. Three files are saved to `runs/<timestamp>/`.

**Total expected time:** 30–90 seconds.

---

## 9.7 How to inspect the saved outputs

After the run completes, check what was saved:
```bash
ls -la runs/
```
You will see a folder named with a timestamp (e.g., `20240115_143022`). Inspect it:
```bash
# List contents of the run folder (replace timestamp with your actual folder name)
ls -la runs/20240115_143022/

# Read the builder's draft
cat runs/20240115_143022/01_builder_draft.txt

# Read the critic's review
cat runs/20240115_143022/02_critic_review.txt
```

Or open the whole runs folder in VS Code:
```bash
code runs/
```

---

## 9.8 How to tell if the critique is useful

A **useful critique** is specific and actionable. Signs it is working:

**Good critique — what it looks like:**
```
Issue: The explanation skips the attention mechanism entirely.
Location: Paragraphs 2–3
Fix: Add a section explaining what "attention" means and why it matters
     before describing encoder/decoder structure.

Issue: The code example is missing import statements.
Location: Code block near the end
Fix: Add "import torch" and "from transformers import ..." at the top.

Overall: The draft covers the basics but has significant gaps that would
confuse a developer trying to understand transformers in practice.
```

**Poor critique — what to fix:**
```
The draft is good overall but could be improved in some areas.
Consider making it more detailed and clearer.
```

If your critique looks like the poor example (vague, no specific issues), the
`prompts/critic.txt` system prompt needs strengthening. Open it and add:

```
IMPORTANT: Each issue must name the specific paragraph or section it refers to.
Each fix must describe the exact change needed, not a general suggestion.
Vague criticism like "make it clearer" is not acceptable — explain what is
unclear and why.
```

---

## 9.9 Common problems and fixes

**Problem: `ModuleNotFoundError: No module named 'agents'`**

Symptom: Running `python run_phase2.py` gives this error.

Cause: You are not running from the project root, so Python cannot find the
`agents/` package.

Fix:
```bash
pwd
```
You must be in `/Users/andyyaro/Downloads/multi-modal-workflow`. If you are not:
```bash
cd ~/Downloads/multi-modal-workflow
python run_phase2.py --goal "your goal"
```

---

**Problem: `FileNotFoundError: Prompt template not found: prompts/builder.txt`**

Cause: The prompt file is empty or was not saved correctly.

Fix:
```bash
cat prompts/builder.txt
```
If it is empty, open the file and add the template from Section 9.4.

---

**Problem: Builder output is very short (2–3 sentences)**

Cause: The model interpreted the prompt as a question to answer briefly rather
than a task to complete in full.

Fix: Strengthen the Builder prompt. Open `prompts/builder.txt` and add to the end:
```
CRITICAL: Write the COMPLETE, FULL deliverable. Do not summarize. Do not
truncate. Write every section described in the plan, fully and in detail.
A response of fewer than 300 words is never acceptable unless the task
explicitly requires brevity.
```

---

**Problem: Critic says everything is perfect**

Cause: The Critic model is being sycophantic (agreeing that the draft is great
to avoid conflict). This is a known behavior in smaller instruction-tuned models.

Fix: Add a negative framing instruction to `prompts/critic.txt`:
```
IMPORTANT: Your job is to find problems, not to praise. If you cannot find
at least three specific, concrete issues to improve, you are not looking
carefully enough. Every draft has room for improvement. Be rigorous.
```

---

**Problem: Runs folder is empty after running the script**

Cause: The script errored before saving files, or the `runs/` directory does not
exist.

Fix:
```bash
mkdir -p runs
python run_phase2.py --goal "test"
```
Check the terminal output for any error messages that appeared before the save step.

---

## 9.10 Phase 2 success criteria

You have passed Phase 2 when:
- [ ] `python run_phase2.py --goal "..."` runs without errors.
- [ ] The Builder produces a substantive draft (not a 2-sentence answer).
- [ ] The Critic produces specific, numbered issues (not vague praise).
- [ ] Three files are saved in `runs/<timestamp>/`.
- [ ] You can read the saved files with `cat` or in VS Code.

---

*End of Sections 8 and 9.*

---

> **Next sections to write:** Section 10 (Phase 3 — Add Fixer and Judge) and
> Section 11 (Phase 4 — Add the Reiteration Loop).

---

# SECTION 10 — Phase 3: Add Fixer and Judge

You now have Builder → Critic working. In this phase you add two more agents:

- **Fixer** — takes the draft and the critique, produces an improved version.
- **Judge** — scores the fixed draft and returns structured JSON with a pass/fail
  decision.

After this phase, the terminal pipeline is: Builder → Critic → Fixer → Judge.
The loop logic (repeating if the score is too low) comes in Section 11.

---

## 10.1 Write the Fixer agent

**File path:** `agents/fixer.py`

```bash
code agents/fixer.py
```

```python
"""
agents/fixer.py

The Fixer agent takes the original draft and the Critic's feedback,
then produces an improved revised draft that addresses every critique point.
"""

from agents.base_agent import BaseAgent


class FixerAgent(BaseAgent):

    def __init__(self, model: str, **kwargs):
        super().__init__(model=model, role="fixer", **kwargs)

    def run(self, goal: str, draft: str, critique: str, iteration: int = 1) -> str:
        """
        Produce a revised draft that addresses the critique.

        Args:
            goal:      The user's original goal statement.
            draft:     The draft to be improved.
            critique:  The structured critique from the Critic agent.
            iteration: Which revision pass this is (for prompt context).

        Returns:
            The full text of the revised draft.
        """
        system_prompt = self.load_prompt_template()

        full_prompt = f"""{system_prompt}

ORIGINAL GOAL:
{goal}

CURRENT DRAFT (revision {iteration}):
{draft}

CRITIC'S FEEDBACK:
{critique}

Now write the complete improved draft that addresses every issue raised above.
"""
        print(f"  [Fixer] Calling {self.model} (revision {iteration})...")
        result = self.call_model(full_prompt)
        print(f"  [Fixer] Revised draft complete ({len(result)} chars)")
        return result
```

Save the file.

---

## 10.2 Write the Judge agent

The Judge is the most structurally important agent. It must return valid JSON —
not prose, not JSON embedded in markdown, not JSON with commentary around it.
The code handles malformed output with a retry and a fallback parser.

**File path:** `agents/judge.py`

```bash
code agents/judge.py
```

```python
"""
agents/judge.py

The Judge agent scores a draft against the original goal and returns
a structured JSON verdict. It decides whether the output passes the
quality threshold.

Expected JSON output format:
{
    "scores": {
        "completeness": 0-25,
        "accuracy": 0-25,
        "clarity": 0-25,
        "usefulness": 0-25
    },
    "total_score": 0-100,
    "pass": true/false,
    "hard_fails": [],
    "rationale": "One paragraph explaining the score."
}
"""

import json
import re
from agents.base_agent import BaseAgent


PASS_THRESHOLD = 70  # default; overridden by pipeline caller


class JudgeAgent(BaseAgent):

    def __init__(self, model: str, pass_threshold: int = PASS_THRESHOLD, **kwargs):
        super().__init__(model=model, role="judge", **kwargs)
        self.pass_threshold = pass_threshold

    def run(self, goal: str, draft: str, iteration: int = 1) -> dict:
        """
        Score the draft and return a verdict dict.

        Args:
            goal:      The user's original goal statement.
            draft:     The draft to be scored.
            iteration: Which iteration this is (for logging context).

        Returns:
            A dict matching the JSON schema above.
            On unrecoverable parse failure, returns a safe fallback dict.
        """
        system_prompt = self.load_prompt_template()

        full_prompt = f"""{system_prompt}

ORIGINAL GOAL:
{goal}

DRAFT TO SCORE (iteration {iteration}):
{draft}

Return ONLY the JSON object. No explanation, no markdown, no code fences.
"""
        print(f"  [Judge] Calling {self.model} (iteration {iteration})...")

        # Try up to 3 times to get valid JSON
        raw = ""
        for attempt in range(1, 4):
            raw = self.call_model(full_prompt)
            verdict = self._parse_json(raw)
            if verdict is not None:
                verdict = self._validate_and_fix(verdict)
                verdict["pass"] = verdict["total_score"] >= self.pass_threshold
                print(
                    f"  [Judge] Score: {verdict['total_score']}/100 "
                    f"({'PASS' if verdict['pass'] else 'FAIL'})"
                )
                return verdict
            print(f"  [Judge] Attempt {attempt}: could not parse JSON. Retrying...")

        # All attempts failed — return a conservative fallback
        print("  [Judge] WARNING: Could not parse Judge output after 3 attempts.")
        print(f"  [Judge] Raw output was:\n{raw[:500]}")
        return self._fallback_verdict(raw)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _parse_json(self, text: str) -> dict | None:
        """
        Try to extract a JSON object from the model's response.
        Handles: clean JSON, JSON wrapped in ```json ... ```, leading/trailing text.
        """
        # 1. Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 2. Strip markdown code fences and retry
        stripped = re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

        # 3. Find the first {...} block in the text and try to parse it
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        return None

    def _validate_and_fix(self, verdict: dict) -> dict:
        """
        Ensure required keys exist and values are in range.
        Fills in safe defaults for any missing fields.
        """
        # Ensure scores dict exists
        if "scores" not in verdict or not isinstance(verdict["scores"], dict):
            verdict["scores"] = {
                "completeness": 15,
                "accuracy": 15,
                "clarity": 15,
                "usefulness": 15,
            }

        # Clamp each score to 0–25
        for key in ["completeness", "accuracy", "clarity", "usefulness"]:
            if key not in verdict["scores"]:
                verdict["scores"][key] = 15
            verdict["scores"][key] = max(0, min(25, int(verdict["scores"].get(key, 15))))

        # Recompute total_score from individual scores (do not trust the model's sum)
        verdict["total_score"] = sum(verdict["scores"].values())

        # Ensure hard_fails is a list
        if "hard_fails" not in verdict or not isinstance(verdict["hard_fails"], list):
            verdict["hard_fails"] = []

        # Ensure rationale is a string
        if "rationale" not in verdict or not isinstance(verdict["rationale"], str):
            verdict["rationale"] = "No rationale provided."

        return verdict

    def _fallback_verdict(self, raw_text: str) -> dict:
        """
        Return a conservative failing verdict when JSON parsing fails entirely.
        Saves the raw output so you can inspect it.
        """
        return {
            "scores": {
                "completeness": 10,
                "accuracy": 10,
                "clarity": 10,
                "usefulness": 10,
            },
            "total_score": 40,
            "pass": False,
            "hard_fails": ["judge_parse_error"],
            "rationale": (
                "The Judge agent returned output that could not be parsed as JSON. "
                "This is treated as a failing score. Raw output saved for inspection."
            ),
            "raw_judge_output": raw_text[:2000],
        }
```

Save the file.

---

## 10.3 Write the prompt templates

**File path:** `prompts/fixer.txt`

```bash
code prompts/fixer.txt
```

```
You are an expert Fixer agent in a multi-agent quality improvement system.

Your job is to take a draft and a set of specific critical feedback, then
produce an improved version that addresses every issue raised.

Rules:
- Read the critique carefully before making any changes.
- Address EVERY specific issue raised by the Critic. Do not skip any.
- Do not just add a sentence to patch a problem — restructure or rewrite
  sections if that is what is needed.
- Maintain everything that was already working well in the original draft.
- Do not introduce new problems while fixing existing ones.
- The revised draft must be complete — not a summary of changes, not a
  diff, but the full revised document ready to be re-evaluated.
- Do not include meta-commentary like "I fixed the following issues..."
  Just produce the improved deliverable directly.
- If the critic raised a point you disagree with, still address it.
  Your job is revision, not debate.
```

Save the file.

---

**File path:** `prompts/judge.txt`

```bash
code prompts/judge.txt
```

```
You are a strict Judge agent in a multi-agent quality improvement system.

Your job is to score a draft against the original goal using a 100-point rubric.
You must return ONLY a valid JSON object — no explanation, no markdown, no preamble.

SCORING RUBRIC (each category is worth 0–25 points):

1. completeness (0–25):
   Does the draft fully address everything the goal asked for?
   25 = nothing is missing
   15 = one or two minor gaps
   5  = significant sections are missing or underdeveloped
   0  = mostly off-topic or incomplete

2. accuracy (0–25):
   Is the content factually correct, logically sound, and free of errors?
   25 = no errors detected
   15 = minor inaccuracies that do not break the core message
   5  = notable factual or logical errors
   0  = fundamentally incorrect or misleading

3. clarity (0–25):
   Is the writing clear, well-structured, and easy to follow?
   25 = excellent structure, flows naturally, no confusing parts
   15 = mostly clear with some awkward or dense sections
   5  = difficult to follow in multiple places
   0  = confusing throughout

4. usefulness (0–25):
   Would the intended audience find this genuinely useful and actionable?
   25 = immediately useful, meets the need precisely
   15 = useful but could be more targeted or practical
   5  = limited practical value
   0  = not useful to the intended audience

HARD FAILS (automatic failure regardless of score):
- Broken code that will not run (coding tasks only)
- Dangerous or harmful content
- Completely off-topic response
- Plagiarized or fabricated citations

Return ONLY this JSON object, with no text before or after it:

{
    "scores": {
        "completeness": <integer 0–25>,
        "accuracy": <integer 0–25>,
        "clarity": <integer 0–25>,
        "usefulness": <integer 0–25>
    },
    "total_score": <integer 0–100, must equal sum of scores>,
    "pass": <true if total_score >= 70, false otherwise>,
    "hard_fails": [<list of strings describing any hard failures, or empty list>],
    "rationale": "<one paragraph explaining the scores>"
}
```

Save the file.

---

## 10.4 Write the four-agent pipeline script

**File path:** `run_phase3.py`

```bash
code run_phase3.py
```

```python
"""
run_phase3.py

Phase 3: Four-agent terminal pipeline.
Builder → Critic → Fixer → Judge

Outputs are saved to runs/<timestamp>/.
The Judge returns structured JSON with scores and a pass/fail verdict.

Usage:
    python run_phase3.py --goal "Your goal here"
    python run_phase3.py --goal "Your goal here" --threshold 75
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from agents.builder import BuilderAgent
from agents.critic import CriticAgent
from agents.fixer import FixerAgent
from agents.judge import JudgeAgent


DEFAULT_MODEL_MAIN = "llama3.2:3b"   # Bootstrap default; override with --model-main
DEFAULT_MODEL_FAST = "llama3.2:3b"
DEFAULT_THRESHOLD = 70
RUNS_DIR = Path("runs")


def make_run_dir() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RUNS_DIR / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def save(run_dir: Path, filename: str, content: str):
    path = run_dir / filename
    path.write_text(content, encoding="utf-8")
    print(f"  [Saved] {path}")


def header(label: str):
    print()
    print("=" * 60)
    print(f"  {label}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Phase 3: Builder → Critic → Fixer → Judge"
    )
    parser.add_argument("--goal", required=True)
    parser.add_argument("--model-main", default=DEFAULT_MODEL_MAIN)
    parser.add_argument("--model-fast", default=DEFAULT_MODEL_FAST)
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD,
                        help="Minimum score to pass (0–100, default 70)")
    args = parser.parse_args()

    goal = args.goal.strip()
    run_dir = make_run_dir()

    print()
    print("LOCAL AI ORCHESTRATOR — Phase 3: Builder → Critic → Fixer → Judge")
    print(f"Run dir   : {run_dir}")
    print(f"Goal      : {goal}")
    print(f"Threshold : {args.threshold}/100")

    plan_stub = f"Write a thorough, well-structured response to:\n{goal}"

    # ── BUILDER ───────────────────────────────────────────────────────────────
    header("STEP 1 / 4: BUILDER")
    builder = BuilderAgent(model=args.model_main)
    draft = builder.run(goal=goal, plan=plan_stub)
    save(run_dir, "01_builder_draft.txt", draft)
    print("\nDRAFT PREVIEW (first 400 chars):")
    print(draft[:400] + ("..." if len(draft) > 400 else ""))

    # ── CRITIC ────────────────────────────────────────────────────────────────
    header("STEP 2 / 4: CRITIC")
    critic = CriticAgent(model=args.model_fast)
    critique = critic.run(goal=goal, draft=draft)
    save(run_dir, "02_critic_review.txt", critique)
    print("\nCRITIQUE PREVIEW (first 400 chars):")
    print(critique[:400] + ("..." if len(critique) > 400 else ""))

    # ── FIXER ─────────────────────────────────────────────────────────────────
    header("STEP 3 / 4: FIXER")
    fixer = FixerAgent(model=args.model_main)
    revised = fixer.run(goal=goal, draft=draft, critique=critique, iteration=1)
    save(run_dir, "03_fixer_revision_v1.txt", revised)
    print("\nREVISION PREVIEW (first 400 chars):")
    print(revised[:400] + ("..." if len(revised) > 400 else ""))

    # ── JUDGE ─────────────────────────────────────────────────────────────────
    header("STEP 4 / 4: JUDGE")
    judge = JudgeAgent(model=args.model_main, pass_threshold=args.threshold)
    verdict = judge.run(goal=goal, draft=revised, iteration=1)
    save(run_dir, "04_judge_verdict_v1.json", json.dumps(verdict, indent=2))

    # ── SUMMARY ───────────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  VERDICT")
    print("=" * 60)
    print(f"  Total score  : {verdict['total_score']}/100")
    print(f"  Pass/Fail    : {'✓ PASS' if verdict['pass'] else '✗ FAIL'}")
    print(f"  Threshold    : {args.threshold}/100")
    print()
    print("  Category scores:")
    for cat, score in verdict.get("scores", {}).items():
        print(f"    {cat:<16} {score}/25")
    if verdict.get("hard_fails"):
        print(f"\n  Hard fails: {verdict['hard_fails']}")
    print()
    print(f"  Rationale: {verdict.get('rationale', 'N/A')}")
    print()
    print(f"  Run saved to: {run_dir}/")
    print()
    if verdict["pass"]:
        print("  Result: Output passed the quality threshold.")
        print("  Next: Add the reiteration loop (Phase 4).")
    else:
        print(f"  Result: Score {verdict['total_score']} is below threshold {args.threshold}.")
        print("  Next: Add the reiteration loop to auto-improve (Phase 4).")


if __name__ == "__main__":
    main()
```

Save the file.

---

## 10.5 Run the four-agent pipeline

```bash
python run_phase3.py --goal "Explain the difference between supervised and unsupervised learning in machine learning. Include one practical example of each."
```

**Expected terminal flow:**
1. Builder writes a draft (~20–40s).
2. Critic reviews it (~10–20s).
3. Fixer produces a revised version (~20–40s).
4. Judge scores the revision and returns JSON (~20–40s).
5. Summary prints with score breakdown.

**Expected score range:** 55–85 on a first-pass revision. Scores below 70 are common
on the first try — that is exactly why the loop in Phase 4 exists.

**Verify the saved files:**
```bash
ls runs/$(ls -t runs/ | head -1)/
```
**What this does:** Lists files inside the most recently created run folder.

Expected:
```
01_builder_draft.txt
02_critic_review.txt
03_fixer_revision_v1.txt
04_judge_verdict_v1.json
```

**Inspect the verdict JSON:**
```bash
cat runs/$(ls -t runs/ | head -1)/04_judge_verdict_v1.json
```

Expected output:
```json
{
  "scores": {
    "completeness": 20,
    "accuracy": 18,
    "clarity": 17,
    "usefulness": 19
  },
  "total_score": 74,
  "pass": true,
  "hard_fails": [],
  "rationale": "The revised draft adequately covers both learning types..."
}
```

---

## 10.6 JSON parsing: what can go wrong and how each case is handled

The Judge agent's `_parse_json()` method handles four failure modes:

| Failure mode | Example | How the code handles it |
|---|---|---|
| Clean JSON returned | `{"total_score": 74, ...}` | `json.loads()` succeeds directly |
| JSON in code fence | ` ```json\n{...}\n``` ` | Strips fences, retries parse |
| JSON with leading text | `Here is my score:\n{...}` | Finds `{...}` block with regex |
| Completely garbled | `I think this draft is...` | Returns `_fallback_verdict()` after 3 attempts |

If you see `WARNING: Could not parse Judge output after 3 attempts`, inspect the
raw output:
```bash
cat runs/$(ls -t runs/ | head -1)/04_judge_verdict_v1.json | python3 -m json.tool
```

If the file contains `raw_judge_output`, the model produced prose instead of JSON.
Fix: Strengthen the Judge prompt. Open `prompts/judge.txt` and add as the very first
line:

```
CRITICAL INSTRUCTION: You must respond with ONLY a JSON object.
The very first character of your response must be '{'.
The very last character must be '}'.
Any other format will be treated as a failure.
```

---

## 10.7 How to decide whether output passes

The pass/fail logic is in `JudgeAgent._validate_and_fix()`:

```python
verdict["pass"] = verdict["total_score"] >= self.pass_threshold
```

The default threshold is 70/100. You can change it per run:
```bash
python run_phase3.py --goal "..." --threshold 80
```

Or change the default in `run_phase3.py`:
```python
DEFAULT_THRESHOLD = 75
```

**When to raise or lower the threshold:**

- **Raise to 80+** for important deliverables where you want multiple revision cycles.
- **Lower to 60** during development and testing to let the pipeline complete
  quickly while you are still tuning prompts.
- **Never set below 50** — a score below 50 typically means the output has
  fundamental problems that more loops will not fix. Consider rephrasing the goal.

---

## 10.8 Phase 3 success criteria

You have passed Phase 3 when:
- [ ] `python run_phase3.py --goal "..."` runs end-to-end without errors.
- [ ] All four files are saved in `runs/<timestamp>/`.
- [ ] The Judge returns a valid JSON verdict (not the fallback).
- [ ] The JSON contains `total_score`, `pass`, `scores`, and `rationale`.
- [ ] You can change `--threshold` and the pass/fail changes accordingly.

---

# SECTION 11 — Phase 4: Add the Reiteration Loop

This is the core of the system. The loop repeats (Critic → Fixer → Judge) until
the output passes, the max loop count is reached, or improvement stalls.

---

## 11.1 Pseudocode for the loop

```
goal = user input
run_dir = new timestamped folder

draft = Builder(goal)                   # version 1 draft
save(draft, "01_builder_draft.txt")

iteration = 1
best_score = 0
best_draft = draft
stop_reason = ""

LOOP:
    critique = Critic(goal, draft)
    save(critique, f"critique_v{iteration}.txt")

    revised = Fixer(goal, draft, critique, iteration)
    save(revised, f"revision_v{iteration}.txt")

    verdict = Judge(goal, revised, iteration)
    save(verdict, f"verdict_v{iteration}.json")

    score = verdict["total_score"]

    if score > best_score:
        best_score = score
        best_draft = revised

    if verdict["pass"]:
        stop_reason = "passed"
        break

    if iteration >= MAX_LOOPS:
        stop_reason = "max_loops"
        break

    improvement = score - previous_score
    if iteration > 1 and improvement < MIN_IMPROVEMENT:
        stop_reason = "stalled"
        break

    previous_score = score
    draft = revised          # feed revision back as new draft
    iteration += 1

final = Synthesizer(goal, best_draft)
save(final, "final_output.txt")
print summary
```

---

## 11.2 Write the remaining agent files

Before writing the loop script, add the agents not yet implemented.

**File path:** `agents/supervisor.py`

```bash
code agents/supervisor.py
```

```python
"""
agents/supervisor.py

The Supervisor agent receives the raw user goal and returns a refined,
unambiguous problem statement plus a routing decision (which mode to use).
For the MVP, it returns the goal with light cleanup and defaults to "general".
"""

from agents.base_agent import BaseAgent


class SupervisorAgent(BaseAgent):

    def __init__(self, model: str, **kwargs):
        super().__init__(model=model, role="supervisor", **kwargs)

    def run(self, goal: str) -> dict:
        """
        Refine the user goal and determine workflow mode.

        Returns:
            dict with keys: refined_goal (str), mode (str)
        """
        system_prompt = self.load_prompt_template()

        full_prompt = f"""{system_prompt}

USER'S RAW GOAL:
{goal}

Return your response as two clearly labeled sections:
REFINED GOAL: <one clear problem statement>
MODE: <one of: writing, coding, planning, debugging, study, general>
"""
        print(f"  [Supervisor] Calling {self.model}...")
        raw = self.call_model(full_prompt)

        refined_goal = goal  # fallback
        mode = "general"

        for line in raw.splitlines():
            if line.upper().startswith("REFINED GOAL:"):
                refined_goal = line.split(":", 1)[1].strip()
            elif line.upper().startswith("MODE:"):
                mode_raw = line.split(":", 1)[1].strip().lower()
                if mode_raw in {"writing", "coding", "planning",
                                "debugging", "study", "general"}:
                    mode = mode_raw

        print(f"  [Supervisor] Mode: {mode} | Goal: {refined_goal[:80]}")
        return {"refined_goal": refined_goal, "mode": mode}
```

---

**File path:** `agents/planner.py`

```bash
code agents/planner.py
```

```python
"""
agents/planner.py

The Planner agent receives the refined goal and produces a step-by-step
plan that the Builder will follow.
"""

from agents.base_agent import BaseAgent


class PlannerAgent(BaseAgent):

    def __init__(self, model: str, **kwargs):
        super().__init__(model=model, role="planner", **kwargs)

    def run(self, goal: str, mode: str = "general") -> str:
        """
        Produce a structured plan for the Builder to follow.

        Args:
            goal: The refined goal from the Supervisor.
            mode: Workflow mode (writing, coding, planning, etc.)

        Returns:
            A numbered plan as plain text.
        """
        system_prompt = self.load_prompt_template()

        full_prompt = f"""{system_prompt}

REFINED GOAL:
{goal}

MODE: {mode}

Produce the step-by-step plan now. Number each step. Be specific.
"""
        print(f"  [Planner] Calling {self.model}...")
        result = self.call_model(full_prompt)
        print(f"  [Planner] Plan complete ({len(result)} chars)")
        return result
```

---

**File path:** `agents/synthesizer.py`

```bash
code agents/synthesizer.py
```

```python
"""
agents/synthesizer.py

The Final Synthesizer polishes the best-scoring draft into a clean,
presentation-ready final output.
"""

from agents.base_agent import BaseAgent


class SynthesizerAgent(BaseAgent):

    def __init__(self, model: str, **kwargs):
        super().__init__(model=model, role="synthesizer", **kwargs)

    def run(self, goal: str, best_draft: str, score: int,
            iterations: int) -> str:
        """
        Polish the best draft into the final deliverable.

        Args:
            goal:       The original user goal.
            best_draft: The highest-scoring draft from the loop.
            score:      The score of the best draft.
            iterations: How many loop iterations were completed.

        Returns:
            The polished final output as a string.
        """
        system_prompt = self.load_prompt_template()

        full_prompt = f"""{system_prompt}

ORIGINAL GOAL:
{goal}

BEST DRAFT (score {score}/100 after {iterations} iteration(s)):
{best_draft}

Polish this draft into the final, presentation-ready deliverable now.
"""
        print(f"  [Synthesizer] Calling {self.model}...")
        result = self.call_model(full_prompt)
        print(f"  [Synthesizer] Final output complete ({len(result)} chars)")
        return result
```

---

## 11.3 Write the remaining prompt templates

**`prompts/supervisor.txt`:**
```bash
code prompts/supervisor.txt
```
```
You are a Supervisor agent in a multi-agent quality improvement system.

Your job is to receive a raw user goal and:
1. Rewrite it as a single, unambiguous, well-formed problem statement.
2. Determine which workflow mode is most appropriate.

Modes:
- writing:   Essays, blog posts, explanations, documentation, creative writing.
- coding:    Writing new code, functions, scripts, or programs.
- planning:  Roadmaps, project plans, strategy, decision frameworks.
- debugging: Diagnosing errors in existing code or reasoning.
- study:     Explaining concepts, summaries, learning guides.
- general:   Anything else or mixed tasks.

Rules:
- If the goal is already clear, keep the refined version close to the original.
- If the goal is vague, make it more specific and actionable.
- Do not add constraints the user did not ask for.
- Do not change the intent — only clarify it.
```

---

**`prompts/planner.txt`:**
```bash
code prompts/planner.txt
```
```
You are a Planner agent in a multi-agent quality improvement system.

Your job is to take a clear goal and produce a structured, numbered plan
that the Builder agent will follow to create the deliverable.

Rules:
- Write 4–8 numbered steps. Not fewer, not more (unless the task genuinely
  requires it).
- Each step should describe a concrete section or action, not an abstract idea.
- For writing tasks: plan the structure (intro, sections, conclusion).
- For coding tasks: plan the architecture (data model, functions, I/O, tests).
- For planning tasks: list the main phases or decision points.
- For debugging tasks: list the hypotheses to test, in order.
- For study tasks: plan the explanation arc (simple → complex, concept → example).
- Do not write any content yet — only the plan.
- Each step should be 1–2 sentences describing what that section should contain.
```

---

**`prompts/synthesizer.txt`:**
```bash
code prompts/synthesizer.txt
```
```
You are a Final Synthesizer agent in a multi-agent quality improvement system.

You receive the best version of a draft that has already been through critique
and revision. Your job is to polish it into a clean, final deliverable.

Rules:
- Do not change the substance or structure — it has already been validated.
- Fix any remaining awkward phrasing, grammatical issues, or formatting problems.
- Improve transitions between sections if they feel abrupt.
- Make sure headings, lists, and code blocks are consistently formatted.
- Remove any meta-commentary or artifacts from the revision process
  (e.g., "In response to the feedback..." or "As the critic noted...").
- The output should read as if it was written by a single expert, not assembled
  by multiple agents.
- Do not shorten the content. Do not remove sections. Only polish what is there.
```

---

## 11.4 Write the full reiteration loop — `run.py`

This is the main entry point for the complete terminal MVP. It includes the full
Supervisor → Planner → Builder → (Critic → Fixer → Judge) loop → Synthesizer
pipeline.

**File path:** `run.py`

```bash
code run.py
```

```python
"""
run.py

Main entry point for the Local AI Orchestrator terminal pipeline.

Pipeline:
  Supervisor → Planner → Builder → [Critic → Fixer → Judge] × N → Synthesizer

The loop repeats until the Judge passes the output, max loops is reached,
or improvement stalls.

Usage:
    python run.py --goal "Your goal here"
    python run.py --goal "..." --max-loops 5 --threshold 75
    python run.py --goal "..." --model-main llama3.1:8b --model-fast llama3.2:3b
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from agents.supervisor import SupervisorAgent
from agents.planner import PlannerAgent
from agents.builder import BuilderAgent
from agents.critic import CriticAgent
from agents.fixer import FixerAgent
from agents.judge import JudgeAgent
from agents.synthesizer import SynthesizerAgent


# ── Defaults ──────────────────────────────────────────────────────────────────
# These are fallback constants only. The actual models come from config/models.yaml
# via get_model_for_role(). Switch active_profile there to change quality level.
DEFAULT_MODEL_MAIN = "llama3.2:3b"   # Bootstrap — override via --model-main
DEFAULT_MODEL_FAST = "llama3.2:3b"
DEFAULT_MAX_LOOPS = 3
DEFAULT_THRESHOLD = 70
DEFAULT_MIN_IMPROVEMENT = 5   # stop looping if score improves by less than this

RUNS_DIR = Path("runs")


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_run_dir() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RUNS_DIR / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def save(run_dir: Path, filename: str, content: str):
    path = run_dir / filename
    path.write_text(content, encoding="utf-8")
    print(f"    → saved: {path.name}")


def header(step: str, label: str):
    print()
    print("╔" + "═" * 58 + "╗")
    print(f"║  {step:<8} {label:<46}  ║")
    print("╚" + "═" * 58 + "╝")


def score_bar(score: int, width: int = 40) -> str:
    """Render a simple ASCII progress bar for the score."""
    filled = int(score / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {score}/100"


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(
    goal: str,
    model_main: str,
    model_fast: str,
    max_loops: int,
    threshold: int,
    min_improvement: int,
    run_dir: Path,
) -> dict:
    """
    Execute the full pipeline and return a summary dict.
    """

    summary = {
        "goal": goal,
        "model_main": model_main,
        "model_fast": model_fast,
        "threshold": threshold,
        "max_loops": max_loops,
        "iterations_run": 0,
        "scores": [],
        "stop_reason": "",
        "final_score": 0,
        "passed": False,
    }

    # ── SUPERVISOR ────────────────────────────────────────────────────────────
    header("STEP 1", "SUPERVISOR — Refine goal & choose mode")
    supervisor = SupervisorAgent(model=model_fast)
    sup_result = supervisor.run(goal=goal)
    refined_goal = sup_result["refined_goal"]
    mode = sup_result["mode"]
    save(run_dir, "00_supervisor.json", json.dumps(sup_result, indent=2))
    print(f"    Refined goal : {refined_goal}")
    print(f"    Mode         : {mode}")

    # ── PLANNER ───────────────────────────────────────────────────────────────
    header("STEP 2", "PLANNER — Create execution plan")
    planner = PlannerAgent(model=model_fast)
    plan = planner.run(goal=refined_goal, mode=mode)
    save(run_dir, "01_planner_plan.txt", plan)
    print(f"    Plan length  : {len(plan)} chars")

    # ── BUILDER (first draft) ─────────────────────────────────────────────────
    header("STEP 3", "BUILDER — Write first draft")
    builder = BuilderAgent(model=model_main)
    draft = builder.run(goal=refined_goal, plan=plan)
    save(run_dir, "02_builder_draft_v0.txt", draft)
    print(f"    Draft length : {len(draft)} chars")

    # ── IMPROVEMENT LOOP ──────────────────────────────────────────────────────
    best_draft = draft
    best_score = 0
    previous_score = 0
    stop_reason = "max_loops"

    critic = CriticAgent(model=model_fast)
    fixer = FixerAgent(model=model_main)
    judge = JudgeAgent(model=model_main, pass_threshold=threshold)

    for iteration in range(1, max_loops + 1):
        summary["iterations_run"] = iteration

        header(f"LOOP {iteration}/{max_loops}", "CRITIC → FIXER → JUDGE")

        # Critic
        print(f"  [Critic] Reviewing draft (iteration {iteration})...")
        critique = critic.run(goal=refined_goal, draft=draft)
        save(run_dir, f"loop{iteration:02d}_critic.txt", critique)

        # Fixer
        revised = fixer.run(
            goal=refined_goal, draft=draft,
            critique=critique, iteration=iteration
        )
        save(run_dir, f"loop{iteration:02d}_fixer.txt", revised)

        # Judge
        verdict = judge.run(goal=refined_goal, draft=revised, iteration=iteration)
        save(run_dir, f"loop{iteration:02d}_judge.json", json.dumps(verdict, indent=2))

        score = verdict["total_score"]
        summary["scores"].append(score)
        print(f"    Score: {score_bar(score)}")

        # Track best
        if score > best_score:
            best_score = score
            best_draft = revised
            save(run_dir, "best_draft.txt", best_draft)

        # Stop conditions
        if verdict["pass"]:
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

    else:
        stop_reason = f"max_loops ({max_loops}) reached"

    # ── FINAL SYNTHESIZER ─────────────────────────────────────────────────────
    header("FINAL", "SYNTHESIZER — Polish best draft")
    synthesizer = SynthesizerAgent(model=model_main)
    final_output = synthesizer.run(
        goal=refined_goal,
        best_draft=best_draft,
        score=best_score,
        iterations=summary["iterations_run"],
    )
    save(run_dir, "final_output.txt", final_output)

    summary["stop_reason"] = stop_reason
    summary["final_score"] = best_score
    summary["passed"] = best_score >= threshold
    save(run_dir, "run_summary.json", json.dumps(summary, indent=2))

    return summary, final_output


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Local AI Orchestrator — full terminal pipeline"
    )
    parser.add_argument("--goal", required=True,
                        help="The goal or task for the pipeline.")
    parser.add_argument("--model-main", default=DEFAULT_MODEL_MAIN,
                        help=f"Main model (Builder/Fixer/Judge). Default: {DEFAULT_MODEL_MAIN}")
    parser.add_argument("--model-fast", default=DEFAULT_MODEL_FAST,
                        help=f"Fast model (Supervisor/Planner/Critic). Default: {DEFAULT_MODEL_FAST}")
    parser.add_argument("--max-loops", type=int, default=DEFAULT_MAX_LOOPS,
                        help=f"Max improvement loops. Default: {DEFAULT_MAX_LOOPS}")
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD,
                        help=f"Pass score (0–100). Default: {DEFAULT_THRESHOLD}")
    parser.add_argument("--min-improvement", type=int, default=DEFAULT_MIN_IMPROVEMENT,
                        help=f"Min score gain per loop before stopping. Default: {DEFAULT_MIN_IMPROVEMENT}")
    args = parser.parse_args()

    run_dir = make_run_dir()

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║         LOCAL AI ORCHESTRATOR — TERMINAL MVP            ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  Goal        : {args.goal[:70]}")
    print(f"  Main model  : {args.model_main}")
    print(f"  Fast model  : {args.model_fast}")
    print(f"  Max loops   : {args.max_loops}")
    print(f"  Threshold   : {args.threshold}/100")
    print(f"  Run dir     : {run_dir}")

    start = datetime.now()

    try:
        summary, final_output = run_pipeline(
            goal=args.goal,
            model_main=args.model_main,
            model_fast=args.model_fast,
            max_loops=args.max_loops,
            threshold=args.threshold,
            min_improvement=args.min_improvement,
            run_dir=run_dir,
        )
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Run stopped by user.")
        print(f"Partial output saved to: {run_dir}/")
        sys.exit(0)

    elapsed = (datetime.now() - start).seconds

    # ── FINAL OUTPUT ──────────────────────────────────────────────────────────
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                    FINAL OUTPUT                         ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    print(final_output)

    # ── RUN SUMMARY ───────────────────────────────────────────────────────────
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                    RUN SUMMARY                          ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  Stop reason   : {summary['stop_reason']}")
    print(f"  Final score   : {score_bar(summary['final_score'])}")
    print(f"  Passed        : {'YES ✓' if summary['passed'] else 'NO ✗'}")
    print(f"  Loops run     : {summary['iterations_run']} / {args.max_loops}")

    if summary["scores"]:
        score_history = " → ".join(str(s) for s in summary["scores"])
        print(f"  Score history : {score_history}")

    print(f"  Time elapsed  : {elapsed}s")
    print(f"  Run saved to  : {run_dir}/")
    print()


if __name__ == "__main__":
    main()
```

Save the file.

---

## 11.5 Run the full pipeline

```bash
python run.py --goal "Write a technical explanation of how Git rebasing works, with a concrete example showing before and after states. Target audience: developers who know Git basics but have never used rebase."
```

For a faster test (smaller model, lower threshold, one loop):
```bash
python run.py \
    --goal "Write three tips for writing cleaner Python code." \
    --model-main llama3.2:3b \
    --model-fast llama3.2:3b \
    --max-loops 1 \
    --threshold 50
```
**What `\` does here:** Continues a long command across multiple lines so it is
easier to read. The shell treats it as one unbroken command.

---

## 11.6 Example saved file tree after a 2-loop run

```
runs/20240115_153042/
├── 00_supervisor.json          ← refined goal and mode
├── 01_planner_plan.txt         ← numbered plan
├── 02_builder_draft_v0.txt     ← initial draft
├── loop01_critic.txt           ← first critique
├── loop01_fixer.txt            ← first revision
├── loop01_judge.json           ← first verdict (e.g. score 62, FAIL)
├── loop02_critic.txt           ← second critique
├── loop02_fixer.txt            ← second revision
├── loop02_judge.json           ← second verdict (e.g. score 78, PASS)
├── best_draft.txt              ← highest-scoring revision
├── final_output.txt            ← polished final deliverable
└── run_summary.json            ← metadata: scores, stop reason, elapsed time
```

---

## 11.7 Handling loop edge cases

### If the loop gets stuck (same score every iteration)

The `min_improvement` guard handles this. If the score does not improve by at
least `DEFAULT_MIN_IMPROVEMENT` (5 points) between iterations, the loop stops
with `stop_reason: stalled`. To change the sensitivity:
```bash
python run.py --goal "..." --min-improvement 3
```
Setting `--min-improvement 0` disables the stall check entirely (loop only stops
on pass or max_loops).

### If quality gets worse after revision

This happens when the Fixer "over-corrects" — changing things that were already
good. The `best_draft` tracking handles this: even if iteration 3 scores lower
than iteration 2, `best_draft.txt` always holds the highest-scored version.
The Synthesizer always works from `best_draft`, not the most recent draft.

### If the Judge is too harsh (everything fails)

Symptoms: Scores cluster in the 30–50 range. Nothing ever passes even after 5
loops. Fix options:
1. Lower `--threshold` to 60 temporarily to understand the scoring pattern.
2. Open `prompts/judge.txt` and soften the rubric descriptions (change "25 = nothing
   is missing" to "25 = covers all major points").
3. Switch the Judge model to `llama3.2:3b` temporarily — smaller models tend
   to be less harsh.

### If the Judge is too easy (everything passes on first try)

Symptoms: First revision always scores 85+. The loop never repeats. Fix options:
1. Raise `--threshold` to 80 or 85.
2. Switch to a stricter Judge model — try `phi4:14b` (Serious Work profile) for
   more demanding structured evaluation.
3. Add harder rubric criteria to `prompts/judge.txt` specific to your task type.

### If the model returns malformed JSON from the Judge

The three-retry logic in `JudgeAgent.run()` handles this automatically. If all
three attempts fail, the fallback verdict returns score 40 (fail) with
`hard_fails: ["judge_parse_error"]`, which forces another loop iteration
(or stops if max loops is reached). Inspect the raw output:
```bash
cat runs/$(ls -t runs/ | head -1)/loop01_judge.json
```
If you see `raw_judge_output` in the JSON, the model did not return JSON at all.
Revisit Section 10.6 for prompt strengthening steps.

---

## 11.8 Phase 4 success criteria

You have a working terminal MVP when:
- [ ] `python run.py --goal "..."` runs the full pipeline end-to-end.
- [ ] The loop repeats at least once on a goal with `--threshold 80`.
- [ ] `best_draft.txt` always contains the highest-scoring version.
- [ ] The loop stops correctly for all three reasons: pass, max_loops, stalled.
- [ ] `run_summary.json` contains accurate scores, stop_reason, and iterations_run.
- [ ] `final_output.txt` contains polished prose (not raw draft text).
- [ ] `Control + C` during a run saves partial output gracefully.

---

*End of Sections 10 and 11.*

---

> **Next sections to write:** Section 12 (Phase 5 — LangGraph) and
> Section 13 (Phase 6 — Streamlit Dashboard).

---

# SECTION 12 — Phase 5: Add LangGraph

Only attempt this section after `python run.py` works end-to-end. LangGraph adds
structured state management and explicit graph topology to the pipeline. It does not
replace your working agents — it wraps them in a framework that makes the flow
inspectable, debuggable, and extensible.

---

## 12.1 Why LangGraph is useful

Your plain Python loop in `run.py` works, but it has a hidden problem: control flow
is implicit. To understand what happens next, you must read the `if/elif/break` logic
scattered through the loop body. Adding a new agent or a new stop condition means
touching multiple places in the same function.

LangGraph makes the pipeline into an explicit **graph**:

- Each agent is a **node** — a named function that receives state and returns updated
  state.
- The transitions between agents are **edges** — either unconditional (always go to
  the next node) or **conditional** (go to node A or node B based on state values).
- The **state** is a single typed dict that every node reads from and writes to.
  Nothing is passed via function arguments — everything flows through state.

Benefits for this project:
- You can visualize the graph structure.
- You can inspect the full state after every node fires.
- Adding a new agent is a matter of writing one node function and one edge definition.
- LangGraph handles the retry/loop logic with `conditional_edges`, which is cleaner
  than a `while` loop with multiple `break` conditions.
- Later, if you deploy this to a server, LangGraph supports async execution and
  streaming out of the box.

---

## 12.2 Install LangGraph

With your virtual environment active:
```bash
pip install langgraph langchain-ollama langchain-core
```

Verify the install:
```bash
python -c "import langgraph; print('langgraph OK', langgraph.__version__)"
python -c "from langchain_ollama import OllamaLLM; print('langchain-ollama OK')"
```

If either fails on Python 3.14, switch to Python 3.12 as described in Section 5.9,
then reinstall.

---

## 12.3 What "state" means in LangGraph

State is a Python `TypedDict` — a dictionary with declared key types. Every node
function receives the full current state and returns a partial dict of the keys it
wants to update. LangGraph merges those updates into the state automatically.

For this pipeline, the state carries:
- The original goal and refined goal
- The current draft (updated after Builder and each Fixer pass)
- The most recent critique and verdict
- The best draft and best score seen so far
- The loop iteration counter and scores list
- The stop reason and final output

---

## 12.4 Create the orchestrator folder

```bash
mkdir -p orchestrator
touch orchestrator/__init__.py
touch orchestrator/graph.py
touch orchestrator/state.py
```

---

## 12.5 Write the state definition

**File path:** `orchestrator/state.py`

```bash
code orchestrator/state.py
```

```python
"""
orchestrator/state.py

Defines the shared state object that flows through every node in the
LangGraph pipeline. Every field is optional so nodes can update only
what they produce.
"""

from typing import TypedDict, Optional


class PipelineState(TypedDict, total=False):
    # Input
    goal: str                    # user's raw goal
    refined_goal: str            # supervisor-cleaned goal
    mode: str                    # writing | coding | planning | debugging | study | general

    # Pipeline data
    plan: str                    # planner's numbered plan
    draft: str                   # current working draft (updated each loop)
    critique: str                # most recent critique
    revised: str                 # most recent fixer output
    verdict: dict                # most recent judge verdict dict

    # Loop tracking
    iteration: int               # current loop number (starts at 1)
    max_loops: int               # maximum loops allowed
    threshold: int               # pass score
    min_improvement: int         # minimum score gain before stall stop
    scores: list                 # list of int scores per iteration
    previous_score: int          # score from last iteration (for stall detection)
    best_score: int              # highest score seen across all iterations
    best_draft: str              # draft that achieved best_score

    # Control
    stop_reason: str             # why the loop ended
    should_continue: bool        # True = run another loop iteration

    # Output
    final_output: str            # polished final deliverable

    # Config
    model_main: str
    model_fast: str
    run_dir: str                 # path to run directory for saving files
```

Save the file.

---

## 12.6 Write the graph

**File path:** `orchestrator/graph.py`

```bash
code orchestrator/graph.py
```

```python
"""
orchestrator/graph.py

LangGraph pipeline for the Local AI Orchestrator.

Graph structure:
  supervisor → planner → builder → critic → fixer → judge → router
                                      ↑___________________________|
                                      (if should_continue is True)
                                                    ↓
                                             (if False) synthesizer → END
"""

import json
from pathlib import Path
from typing import Literal

from langgraph.graph import StateGraph, END

from orchestrator.state import PipelineState
from agents.supervisor import SupervisorAgent
from agents.planner import PlannerAgent
from agents.builder import BuilderAgent
from agents.critic import CriticAgent
from agents.fixer import FixerAgent
from agents.judge import JudgeAgent
from agents.synthesizer import SynthesizerAgent


# ── File saving helper ────────────────────────────────────────────────────────

def _save(run_dir: str, filename: str, content: str):
    path = Path(run_dir) / filename
    path.write_text(content, encoding="utf-8")


# ── Node functions ────────────────────────────────────────────────────────────
# Each node receives the full state dict and returns a partial dict
# containing only the keys it wants to update.

def node_supervisor(state: PipelineState) -> dict:
    agent = SupervisorAgent(model=state["model_fast"])
    result = agent.run(goal=state["goal"])
    _save(state["run_dir"], "00_supervisor.json", json.dumps(result, indent=2))
    return {
        "refined_goal": result["refined_goal"],
        "mode": result["mode"],
    }


def node_planner(state: PipelineState) -> dict:
    agent = PlannerAgent(model=state["model_fast"])
    plan = agent.run(goal=state["refined_goal"], mode=state["mode"])
    _save(state["run_dir"], "01_planner_plan.txt", plan)
    return {"plan": plan}


def node_builder(state: PipelineState) -> dict:
    agent = BuilderAgent(model=state["model_main"])
    draft = agent.run(goal=state["refined_goal"], plan=state["plan"])
    _save(state["run_dir"], "02_builder_draft_v0.txt", draft)
    return {
        "draft": draft,
        "best_draft": draft,
        "iteration": 1,
        "scores": [],
        "previous_score": 0,
        "best_score": 0,
        "should_continue": True,
        "stop_reason": "",
    }


def node_critic(state: PipelineState) -> dict:
    iteration = state.get("iteration", 1)
    agent = CriticAgent(model=state["model_fast"])
    critique = agent.run(goal=state["refined_goal"], draft=state["draft"])
    _save(state["run_dir"], f"loop{iteration:02d}_critic.txt", critique)
    return {"critique": critique}


def node_fixer(state: PipelineState) -> dict:
    iteration = state.get("iteration", 1)
    agent = FixerAgent(model=state["model_main"])
    revised = agent.run(
        goal=state["refined_goal"],
        draft=state["draft"],
        critique=state["critique"],
        iteration=iteration,
    )
    _save(state["run_dir"], f"loop{iteration:02d}_fixer.txt", revised)
    return {"revised": revised}


def node_judge(state: PipelineState) -> dict:
    iteration = state.get("iteration", 1)
    threshold = state.get("threshold", 70)

    agent = JudgeAgent(model=state["model_main"], pass_threshold=threshold)
    verdict = agent.run(
        goal=state["refined_goal"],
        draft=state["revised"],
        iteration=iteration,
    )
    _save(state["run_dir"], f"loop{iteration:02d}_judge.json",
          json.dumps(verdict, indent=2))

    score = verdict["total_score"]
    scores = state.get("scores", []) + [score]

    # Track best draft
    best_score = state.get("best_score", 0)
    best_draft = state.get("best_draft", state["revised"])
    if score > best_score:
        best_score = score
        best_draft = state["revised"]
        _save(state["run_dir"], "best_draft.txt", best_draft)

    # Determine whether to continue
    max_loops = state.get("max_loops", 3)
    min_improvement = state.get("min_improvement", 5)
    previous_score = state.get("previous_score", 0)
    should_continue = True
    stop_reason = ""

    if verdict["pass"]:
        should_continue = False
        stop_reason = f"passed (score {score} >= threshold {threshold})"

    elif iteration >= max_loops:
        should_continue = False
        stop_reason = f"max_loops ({max_loops}) reached"

    elif verdict.get("hard_fails"):
        should_continue = False
        stop_reason = f"hard_fail: {verdict['hard_fails']}"

    elif iteration > 1:
        improvement = score - previous_score
        if improvement < min_improvement:
            should_continue = False
            stop_reason = (
                f"stalled (improvement {improvement} < "
                f"min_improvement {min_improvement})"
            )

    return {
        "verdict": verdict,
        "scores": scores,
        "best_score": best_score,
        "best_draft": best_draft,
        "previous_score": score,
        "draft": state["revised"],       # feed revision forward as new draft
        "iteration": iteration + 1,
        "should_continue": should_continue,
        "stop_reason": stop_reason,
    }


def node_synthesizer(state: PipelineState) -> dict:
    agent = SynthesizerAgent(model=state["model_main"])
    final = agent.run(
        goal=state["refined_goal"],
        best_draft=state["best_draft"],
        score=state["best_score"],
        iterations=state.get("iteration", 1) - 1,
    )
    _save(state["run_dir"], "final_output.txt", final)

    summary = {
        "goal": state["goal"],
        "refined_goal": state["refined_goal"],
        "mode": state.get("mode", "general"),
        "model_main": state["model_main"],
        "model_fast": state["model_fast"],
        "iterations_run": state.get("iteration", 1) - 1,
        "scores": state.get("scores", []),
        "best_score": state["best_score"],
        "threshold": state.get("threshold", 70),
        "stop_reason": state.get("stop_reason", ""),
        "passed": state["best_score"] >= state.get("threshold", 70),
    }
    _save(state["run_dir"], "run_summary.json", json.dumps(summary, indent=2))

    return {"final_output": final}


# ── Routing function ──────────────────────────────────────────────────────────

def route_after_judge(state: PipelineState) -> Literal["critic", "synthesizer"]:
    """
    Conditional edge: after Judge, decide whether to loop back to Critic
    or proceed to the Synthesizer.
    """
    if state.get("should_continue", False):
        return "critic"
    return "synthesizer"


# ── Build the graph ───────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(PipelineState)

    # Add nodes
    graph.add_node("supervisor", node_supervisor)
    graph.add_node("planner", node_planner)
    graph.add_node("builder", node_builder)
    graph.add_node("critic", node_critic)
    graph.add_node("fixer", node_fixer)
    graph.add_node("judge", node_judge)
    graph.add_node("synthesizer", node_synthesizer)

    # Add unconditional edges (always proceed to next node)
    graph.add_edge("supervisor", "planner")
    graph.add_edge("planner", "builder")
    graph.add_edge("builder", "critic")
    graph.add_edge("critic", "fixer")
    graph.add_edge("fixer", "judge")

    # Conditional edge after Judge
    graph.add_conditional_edges(
        "judge",
        route_after_judge,
        {
            "critic": "critic",           # loop back
            "synthesizer": "synthesizer", # proceed to finish
        },
    )

    graph.add_edge("synthesizer", END)

    # Set entry point
    graph.set_entry_point("supervisor")

    return graph.compile()
```

Save the file.

---

## 12.7 Write the LangGraph runner script

**File path:** `run_langgraph.py`

```bash
code run_langgraph.py
```

```python
"""
run_langgraph.py

Run the LangGraph version of the pipeline.
Equivalent to run.py but uses the compiled StateGraph instead of
a manual while loop.

Usage:
    python run_langgraph.py --goal "Your goal here"
    python run_langgraph.py --goal "..." --max-loops 4 --threshold 75
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from orchestrator.graph import build_graph


RUNS_DIR = Path("runs")

# Fallback constants only — real models come from config/models.yaml active_profile
DEFAULT_MODEL_MAIN = "llama3.2:3b"   # Bootstrap default
DEFAULT_MODEL_FAST = "llama3.2:3b"
DEFAULT_MAX_LOOPS = 3
DEFAULT_THRESHOLD = 70
DEFAULT_MIN_IMPROVEMENT = 5


def make_run_dir() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RUNS_DIR / f"lg_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def score_bar(score: int, width: int = 40) -> str:
    filled = int(score / 100 * width)
    return f"[{'█' * filled}{'░' * (width - filled)}] {score}/100"


def main():
    parser = argparse.ArgumentParser(
        description="LangGraph pipeline for the Local AI Orchestrator"
    )
    parser.add_argument("--goal", required=True)
    parser.add_argument("--model-main", default=DEFAULT_MODEL_MAIN)
    parser.add_argument("--model-fast", default=DEFAULT_MODEL_FAST)
    parser.add_argument("--max-loops", type=int, default=DEFAULT_MAX_LOOPS)
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD)
    parser.add_argument("--min-improvement", type=int, default=DEFAULT_MIN_IMPROVEMENT)
    args = parser.parse_args()

    run_dir = make_run_dir()

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║      LOCAL AI ORCHESTRATOR — LANGGRAPH PIPELINE         ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  Goal       : {args.goal[:70]}")
    print(f"  Run dir    : {run_dir}")

    # Initial state passed to the graph
    initial_state = {
        "goal": args.goal,
        "model_main": args.model_main,
        "model_fast": args.model_fast,
        "max_loops": args.max_loops,
        "threshold": args.threshold,
        "min_improvement": args.min_improvement,
        "run_dir": str(run_dir),
    }

    app = build_graph()
    start = datetime.now()

    try:
        # stream_mode="values" yields the full state after each node
        for step_output in app.stream(initial_state, stream_mode="values"):
            # Print a progress indicator for each completed node
            # (The state dict grows with each step — we just track the latest)
            if "final_output" in step_output:
                pass  # handled in summary below
            elif "verdict" in step_output and step_output.get("scores"):
                scores = step_output["scores"]
                latest = scores[-1]
                print(f"\n  Loop {len(scores)} score: {score_bar(latest)}")

        final_state = step_output  # last yielded value is the final state

    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Run stopped by user.")
        print(f"Partial output saved to: {run_dir}/")
        sys.exit(0)

    elapsed = (datetime.now() - start).seconds

    # ── Final output ──────────────────────────────────────────────────────────
    final_output = final_state.get("final_output", "[No output produced]")
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                    FINAL OUTPUT                         ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    print(final_output)

    # ── Summary ───────────────────────────────────────────────────────────────
    scores = final_state.get("scores", [])
    best_score = final_state.get("best_score", 0)
    stop_reason = final_state.get("stop_reason", "unknown")
    passed = best_score >= args.threshold

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                    RUN SUMMARY                          ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  Stop reason   : {stop_reason}")
    print(f"  Final score   : {score_bar(best_score)}")
    print(f"  Passed        : {'YES ✓' if passed else 'NO ✗'}")
    print(f"  Loops run     : {len(scores)} / {args.max_loops}")
    if scores:
        print(f"  Score history : {' → '.join(str(s) for s in scores)}")
    print(f"  Time elapsed  : {elapsed}s")
    print(f"  Run saved to  : {run_dir}/")
    print()


if __name__ == "__main__":
    main()
```

Save the file.

---

## 12.8 How to run the LangGraph pipeline

```bash
python run_langgraph.py --goal "Explain the concept of recursion with a Python example."
```

The output and saved files are identical to `run.py`. The difference is internal:
LangGraph manages state transitions instead of your while loop.

---

## 12.9 How to debug LangGraph

**Print the full state after each node:**

Modify the stream loop in `run_langgraph.py` to print state keys after each step:
```python
for step_output in app.stream(initial_state, stream_mode="values"):
    completed_keys = [k for k, v in step_output.items() if v is not None]
    print(f"  [Graph] State keys populated: {completed_keys}")
```

**Visualize the graph structure (requires graphviz):**
```bash
pip install pygraphviz
```
Then in a Python REPL:
```python
from orchestrator.graph import build_graph
app = build_graph()
print(app.get_graph().draw_mermaid())
```
This prints a Mermaid diagram you can paste into https://mermaid.live to visualize
the graph.

**Common LangGraph errors:**

| Error | Cause | Fix |
|---|---|---|
| `ImportError: cannot import name 'StateGraph'` | Wrong langgraph version | `pip install --upgrade langgraph` |
| `KeyError: 'refined_goal'` in a node | Node ran before supervisor populated state | Check `graph.add_edge("supervisor", ...)` is correct |
| `GraphRecursionError: Recursion limit reached` | Loop ran > 25 times | Add `recursion_limit` to `app.invoke()`: `app.invoke(state, {"recursion_limit": 50})` |
| `ValidationError` on state | TypedDict field type mismatch | Check that node return dicts match types in `state.py` |

---

## 12.10 How to keep the plain Python fallback

Keep both `run.py` and `run_langgraph.py`. They are functionally equivalent.
Use `run.py` when:
- You are debugging agent logic (simpler stack traces).
- LangGraph has an import error on your Python version.
- You want to add quick one-off changes without touching the graph definition.

Use `run_langgraph.py` when:
- You want streaming output (easier to add to Streamlit with LangGraph).
- You want to inspect or visualize the graph.
- You are building toward a production deployment.

---

# SECTION 13 — Phase 6: Add Streamlit Dashboard

Build this only after `run.py` works end-to-end. The Streamlit dashboard is a local
web interface that runs in your browser and wraps the same pipeline code.

---

## 13.1 Install Streamlit

```bash
pip install streamlit
```

Verify:
```bash
streamlit --version
```
Expected: `Streamlit, version 1.35.x` or newer.

---

## 13.2 Create the app folder

```bash
mkdir -p app
touch app/__init__.py
touch app/streamlit_app.py
```

---

## 13.3 Write the Streamlit app

**File path:** `app/streamlit_app.py`

```bash
code app/streamlit_app.py
```

```python
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

# Make sure the project root is on sys.path so agents/ can be imported
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

RUNS_DIR = ROOT / "runs"
RUNS_DIR.mkdir(exist_ok=True)

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Local AI Orchestrator",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar — configuration ───────────────────────────────────────────────────

with st.sidebar:
    st.title("⚙️ Configuration")

    model_main = st.selectbox(
        "Builder / Fixer / Synthesizer model",
        options=[
            "qwen2.5:14b",          # Serious Work profile
            "qwen2.5-coder:14b",    # Coding Specialist profile
            "llama3.1:8b",          # Fast profile
            "llama3.2:3b",          # Bootstrap profile
        ],
        index=0,
    )

    model_judge = st.selectbox(
        "Judge model (choose a different family than Builder for independence)",
        options=[
            "phi4:14b",             # Serious Work / Coding profiles
            "llama3.1:8b",          # Fast profile
            "llama3.2:3b",          # Bootstrap profile
        ],
        index=0,
    )

    model_fast = st.selectbox(
        "Fast model (Supervisor / Planner / Critic)",
        options=[
            "llama3.2:3b",          # Bootstrap / default routing
            "llama3.1:8b",          # Serious Work supervisor
            "gemma3:12b",           # Serious Work critic
            "llama3.2:1b",          # Ultra-fast routing only
        ],
        index=0,
    )

    mode = st.selectbox(
        "Workflow mode",
        options=["general", "writing", "coding", "planning", "debugging", "study"],
        index=0,
    )

    max_loops = st.slider("Max improvement loops", min_value=1, max_value=6,
                          value=3, step=1)
    threshold = st.slider("Pass threshold (score / 100)", min_value=50,
                          max_value=95, value=70, step=5)
    min_improvement = st.slider("Min score gain before stall stop",
                                min_value=0, max_value=15, value=5, step=1)

    st.divider()
    st.caption("All models run locally via Ollama.")
    st.caption("No data is sent to external servers.")

# ── Main area ─────────────────────────────────────────────────────────────────

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
    st.caption(f"Estimated time: {max_loops * 60}–{max_loops * 120}s "
               f"· Up to {max_loops} loop{'s' if max_loops > 1 else ''}")

st.divider()


# ── Pipeline runner (runs in thread so UI stays responsive) ───────────────────

def make_run_dir() -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    d = RUNS_DIR / f"ui_{ts}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save(run_dir: Path, filename: str, content: str):
    (run_dir / filename).write_text(content, encoding="utf-8")


def run_pipeline_thread(goal: str, model_main: str, model_fast: str,
                        max_loops: int, threshold: int, min_improvement: int,
                        run_dir: Path, event_queue: Queue):
    """
    Runs the full pipeline in a background thread and posts events to
    event_queue so the Streamlit UI can display them in real time.

    Event format: dict with keys:
        type: "step" | "loop_result" | "final" | "error"
        ... additional keys per type
    """

    def emit(event: dict):
        event_queue.put(event)

    try:
        # Supervisor
        emit({"type": "step", "agent": "Supervisor", "status": "running"})
        supervisor = SupervisorAgent(model=model_fast)
        sup = supervisor.run(goal=goal)
        refined_goal = sup["refined_goal"]
        detected_mode = sup["mode"]
        save(run_dir, "00_supervisor.json", json.dumps(sup, indent=2))
        emit({"type": "step", "agent": "Supervisor", "status": "done",
              "output": f"**Refined goal:** {refined_goal}\n\n**Mode:** {detected_mode}"})

        # Planner
        emit({"type": "step", "agent": "Planner", "status": "running"})
        planner = PlannerAgent(model=model_fast)
        plan = planner.run(goal=refined_goal, mode=detected_mode)
        save(run_dir, "01_planner_plan.txt", plan)
        emit({"type": "step", "agent": "Planner", "status": "done", "output": plan})

        # Builder
        emit({"type": "step", "agent": "Builder", "status": "running"})
        builder = BuilderAgent(model=model_main)
        draft = builder.run(goal=refined_goal, plan=plan)
        save(run_dir, "02_builder_draft_v0.txt", draft)
        emit({"type": "step", "agent": "Builder", "status": "done", "output": draft})

        # Loop
        best_draft = draft
        best_score = 0
        previous_score = 0
        scores = []
        stop_reason = "max_loops"

        critic = CriticAgent(model=model_fast)
        fixer = FixerAgent(model=model_main)
        judge = JudgeAgent(model=model_main, pass_threshold=threshold)

        for iteration in range(1, max_loops + 1):
            emit({"type": "loop_start", "iteration": iteration,
                  "max_loops": max_loops})

            emit({"type": "step", "agent": f"Critic (loop {iteration})",
                  "status": "running"})
            critique = critic.run(goal=refined_goal, draft=draft)
            save(run_dir, f"loop{iteration:02d}_critic.txt", critique)
            emit({"type": "step", "agent": f"Critic (loop {iteration})",
                  "status": "done", "output": critique})

            emit({"type": "step", "agent": f"Fixer (loop {iteration})",
                  "status": "running"})
            revised = fixer.run(goal=refined_goal, draft=draft,
                                critique=critique, iteration=iteration)
            save(run_dir, f"loop{iteration:02d}_fixer.txt", revised)
            emit({"type": "step", "agent": f"Fixer (loop {iteration})",
                  "status": "done", "output": revised})

            emit({"type": "step", "agent": f"Judge (loop {iteration})",
                  "status": "running"})
            verdict = judge.run(goal=refined_goal, draft=revised, iteration=iteration)
            save(run_dir, f"loop{iteration:02d}_judge.json",
                 json.dumps(verdict, indent=2))

            score = verdict["total_score"]
            scores.append(score)

            if score > best_score:
                best_score = score
                best_draft = revised
                save(run_dir, "best_draft.txt", best_draft)

            emit({"type": "loop_result", "iteration": iteration,
                  "score": score, "verdict": verdict, "scores": list(scores)})
            emit({"type": "step", "agent": f"Judge (loop {iteration})",
                  "status": "done",
                  "output": f"Score: **{score}/100** · "
                             f"{'✅ PASS' if verdict['pass'] else '❌ FAIL'}\n\n"
                             f"{verdict.get('rationale', '')}"})

            if verdict["pass"]:
                stop_reason = f"passed (score {score} ≥ threshold {threshold})"
                draft = revised
                break
            if iteration >= max_loops:
                stop_reason = f"max loops ({max_loops}) reached"
                draft = revised
                break
            if iteration > 1:
                if score - previous_score < min_improvement:
                    stop_reason = "stalled (score not improving)"
                    draft = revised
                    break
            if verdict.get("hard_fails"):
                stop_reason = f"hard fail: {verdict['hard_fails']}"
                draft = revised
                break

            previous_score = score
            draft = revised

        # Synthesizer
        emit({"type": "step", "agent": "Synthesizer", "status": "running"})
        synth = SynthesizerAgent(model=model_main)
        final_output = synth.run(goal=refined_goal, best_draft=best_draft,
                                 score=best_score, iterations=len(scores))
        save(run_dir, "final_output.txt", final_output)

        summary = {
            "goal": goal, "refined_goal": refined_goal, "mode": detected_mode,
            "model_main": model_main, "model_fast": model_fast,
            "scores": scores, "best_score": best_score,
            "threshold": threshold, "stop_reason": stop_reason,
            "passed": best_score >= threshold,
        }
        save(run_dir, "run_summary.json", json.dumps(summary, indent=2))

        emit({"type": "final", "output": final_output, "summary": summary,
              "run_dir": str(run_dir)})

    except Exception as exc:
        emit({"type": "error", "message": str(exc)})


# ── UI rendering ──────────────────────────────────────────────────────────────

if run_btn:
    if not goal.strip():
        st.error("Please enter a goal before running.")
        st.stop()

    run_dir = make_run_dir()
    event_queue: Queue = Queue()

    thread = threading.Thread(
        target=run_pipeline_thread,
        args=(goal, model_main, model_fast, max_loops, threshold,
              min_improvement, run_dir, event_queue),
        daemon=True,
    )
    thread.start()

    # ── Live output area ──────────────────────────────────────────────────────
    st.subheader("📡 Live Pipeline Output")

    agent_expanders = {}
    score_placeholder = st.empty()
    scores_so_far = []

    final_placeholder = st.empty()
    summary_placeholder = st.empty()

    # Poll the queue until the thread finishes
    while thread.is_alive() or not event_queue.empty():
        try:
            event = event_queue.get(timeout=0.5)
        except Empty:
            time.sleep(0.1)
            continue

        etype = event.get("type")

        if etype == "step":
            agent = event["agent"]
            status = event["status"]
            output = event.get("output", "")
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
            st.markdown(
                f"---\n**🔄 Loop {event['iteration']} of {event['max_loops']}**"
            )

        elif etype == "loop_result":
            scores_so_far = event["scores"]
            # Redraw score chart
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
                col_a.metric("Final score", f"{summary['best_score']}/100")
                col_b.metric("Passed", "Yes ✓" if summary["passed"] else "No ✗")
                col_c.metric("Loops run", len(summary["scores"]))
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

        elif etype == "error":
            st.error(f"Pipeline error: {event['message']}")
            st.info("Check that Ollama is running and the model is downloaded.")
            break

    if thread.is_alive():
        thread.join(timeout=5)
```

Save the file.

---

## 13.4 How to run the Streamlit dashboard

Make sure your virtual environment is active and Ollama is running. Then:

```bash
streamlit run app/streamlit_app.py
```

**What this does:** Starts a local web server and opens your browser automatically.
If it does not open automatically, go to:
```
http://localhost:8501
```

**To stop the Streamlit server:** Press `Control + C` in the Terminal window where
it is running.

---

## 13.5 What the interface looks like

```
┌─────────────────────────────────────────────────────────────┐
│ Sidebar              │ Main area                            │
│ ─────────────────    │ ──────────────────────────────────── │
│ Main model ▾         │ 🧠 Local AI Orchestrator             │
│ Fast model ▾         │                                      │
│ Workflow mode ▾      │ [Enter your goal or task........]    │
│ Max loops: 3 ────    │ [..................................] │
│ Threshold: 70 ───    │                                      │
│ Min improvement: 5   │ [ ▶ Run Pipeline ]                   │
│                      │                                      │
│                      │ 📡 Live Pipeline Output              │
│                      │  ✅ Supervisor                       │
│                      │  ✅ Planner                          │
│                      │  ⏳ Builder...                       │
│                      │                                      │
│                      │ 📊 Score Progression                 │
│                      │  [line chart of scores]              │
│                      │                                      │
│                      │ ✨ Final Output                      │
│                      │  [polished result text]              │
│                      │  [ 📥 Download ]                     │
│                      │                                      │
│                      │ 📋 Run Summary                       │
│                      │  Score: 78  Passed: Yes  Loops: 2   │
└─────────────────────────────────────────────────────────────┘
```

---

## 13.6 How to reload after code changes

Streamlit auto-reloads when it detects file changes. After saving any `.py` file in
the `app/` or `agents/` folder, look for the "Source file changed. Rerun?" banner
at the top of the browser window and click **Rerun**.

To force a full restart (clears all session state):
```bash
# In Terminal: Ctrl+C to stop, then restart
streamlit run app/streamlit_app.py
```

---

## 13.7 Common Streamlit errors and fixes

**Error: `ModuleNotFoundError: No module named 'agents'`**

Cause: Streamlit is not running from the project root.

Fix: Always run the command from the project root:
```bash
cd ~/Downloads/multi-modal-workflow
streamlit run app/streamlit_app.py
```

---

**Error: `OSError: [Errno 48] Address already in use: ('', 8501)`**

Cause: Another Streamlit server is already running on port 8501.

Fix option A — Kill the existing server:
```bash
lsof -ti :8501 | xargs kill -9
```
**What this does:** Finds the process ID using port 8501 and sends it a kill signal.

Fix option B — Use a different port:
```bash
streamlit run app/streamlit_app.py --server.port 8502
```
Then open `http://localhost:8502` in your browser.

---

**Error: Pipeline output appears all at once instead of streaming**

Cause: Streamlit's threading approach means the UI updates happen as queue events
arrive, but the browser may batch them. This is normal behavior — the agents are
still running sequentially; the display just catches up.

Fix: No fix needed. The events display as each agent completes, which is the correct
behavior.

---

**Error: Browser does not open automatically**

Fix: Open it manually: `http://localhost:8501`

---

**Error: Streamlit shows a blank page after clicking Run**

Cause: An import error in one of the agent files prevented the app from loading.

Fix: Check the Terminal window where `streamlit run` is running. Look for a Python
traceback and fix the import error shown.

---

## 13.8 Phase 6 success criteria

You have a working Streamlit dashboard when:
- [ ] `streamlit run app/streamlit_app.py` opens a browser window at port 8501.
- [ ] Entering a goal and clicking Run starts the pipeline.
- [ ] Each agent's output appears as a collapsible section after it completes.
- [ ] The score chart updates after each Judge verdict.
- [ ] The final output appears at the bottom with a download button.
- [ ] The run summary shows score, pass/fail, and loop count.
- [ ] Files are saved to `runs/ui_<timestamp>/` as expected.
- [ ] `Control + C` in Terminal stops the server cleanly.

---

*End of Sections 12 and 13.*

---

> **Next sections to write:** Section 14 (SQLite Run History) and
> Section 15 (Workflow Modes).

---

# SECTION 14 — Phase 7: Add SQLite Run History

## 14.1 Why SQLite is enough for this project

SQLite is a file-based database. The entire database lives in one `.db` file on your
disk. There is no database server to install, no connection strings to configure, and
no authentication to manage. Python's standard library includes full SQLite support
via the `sqlite3` module — no additional packages needed.

For this project, SQLite is ideal because:
- You are the only user. No concurrent writes, no scaling concerns.
- Run history is read far more often than it is written.
- The database file can be backed up with a single `cp` command.
- If it gets corrupted or you want to start fresh, you delete one file.
- The total data volume (text output from AI runs) will stay well under 1GB for
  years of personal use.

---

## 14.2 What database tables you need

You need two tables:

**`runs`** — one row per pipeline execution:
- run ID, timestamp, goal, mode, model names, final score, pass/fail, stop reason,
  loop count, score history, run directory path.

**`iterations`** — one row per loop iteration within a run:
- foreign key to `runs`, iteration number, critique text, revised draft text,
  judge scores JSON, total score.

This split lets you load the summary of all past runs cheaply (read only `runs`),
and drill into the details of a specific run (join with `iterations`) only when
needed.

---

## 14.3 Create the database module

**File path:** `orchestrator/database.py`

```bash
code orchestrator/database.py
```

```python
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

CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON runs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_iterations_run_id ON iterations(run_id);
"""


# ── Connection helper ─────────────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    """
    Open a connection to the SQLite database.
    Creates the database file and schema if they do not exist.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row      # rows behave like dicts
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")   # safer concurrent reads
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
            iteration, critique, revised_draft, verdict_json, score

    Returns:
        The integer ID of the newly inserted run row.
    """
    init_db()
    conn = get_connection()
    timestamp = datetime.now().isoformat(timespec="seconds")

    cursor = conn.execute(
        """
        INSERT INTO runs
            (timestamp, goal, refined_goal, mode, model_main, model_fast,
             final_score, passed, stop_reason, iterations, scores_json,
             run_dir, final_output)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            timestamp, goal, refined_goal, mode, model_main, model_fast,
            final_score, int(passed), stop_reason,
            len(scores), json.dumps(scores),
            run_dir, final_output,
        ),
    )
    run_id = cursor.lastrowid

    if iterations_data:
        for it in iterations_data:
            conn.execute(
                """
                INSERT INTO iterations
                    (run_id, iteration, critique, revised_draft, verdict_json, score)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    it.get("iteration"),
                    it.get("critique", ""),
                    it.get("revised_draft", ""),
                    json.dumps(it.get("verdict", {})),
                    it.get("score", 0),
                ),
            )

    conn.commit()
    conn.close()
    return run_id


# ── Read operations ───────────────────────────────────────────────────────────

def load_all_runs(limit: int = 50) -> list[dict]:
    """
    Return a list of recent runs, newest first.
    Does not include full text fields (critique, draft) for performance.
    """
    init_db()
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id, timestamp, goal, mode, model_main, final_score,
               passed, stop_reason, iterations, scores_json, run_dir
        FROM runs
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


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
        it = dict(row)
        it["verdict"] = json.loads(it.get("verdict_json") or "{}")
        run["iterations_detail"].append(it)

    conn.close()
    return run


def load_recent_runs(n: int = 10) -> list[dict]:
    """Return the n most recent runs as summary dicts."""
    return load_all_runs(limit=n)


# ── Admin operations ──────────────────────────────────────────────────────────

def delete_run(run_id: int):
    """Delete one run and all its iterations (cascade)."""
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
    conn.executescript("""
        DROP TABLE IF EXISTS iterations;
        DROP TABLE IF EXISTS runs;
    """)
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
```

Save the file.

---

## 14.4 Integrate the database into `run.py`

Open `run.py` and add the database save call at the end of `run_pipeline()`.
Find the line near the bottom of `run_pipeline()` that reads:

```python
    summary["stop_reason"] = stop_reason
```

Just before that line, add the import at the top of the file:
```python
from orchestrator.database import save_run, init_db
```

And add this block at the very end of `run_pipeline()`, after the synthesizer call
and after `save(run_dir, "run_summary.json", ...)`:

```python
    # ── Save to SQLite ────────────────────────────────────────────────────────
    iterations_data = []
    for i, sc in enumerate(summary["scores"], start=1):
        it_critique_path = run_dir / f"loop{i:02d}_critic.txt"
        it_fixer_path = run_dir / f"loop{i:02d}_fixer.txt"
        it_judge_path = run_dir / f"loop{i:02d}_judge.json"
        iterations_data.append({
            "iteration": i,
            "critique": it_critique_path.read_text(encoding="utf-8")
                        if it_critique_path.exists() else "",
            "revised_draft": it_fixer_path.read_text(encoding="utf-8")
                             if it_fixer_path.exists() else "",
            "verdict": json.loads(it_judge_path.read_text(encoding="utf-8"))
                       if it_judge_path.exists() else {},
            "score": sc,
        })

    db_run_id = save_run(
        goal=goal,
        refined_goal=refined_goal,
        mode=mode,
        model_main=model_main,
        model_fast=model_fast,
        final_score=best_score,
        passed=(best_score >= threshold),
        stop_reason=stop_reason,
        scores=summary["scores"],
        run_dir=str(run_dir),
        final_output=final_output,
        iterations_data=iterations_data,
    )
    print(f"    → saved to database (run ID: {db_run_id})")
```

---

## 14.5 How to view run history from the terminal

Create a quick history viewer script:

**File path:** `show_history.py`

```bash
code show_history.py
```

```python
"""
show_history.py

Display recent run history from the SQLite database.

Usage:
    python show_history.py
    python show_history.py --run-id 3
    python show_history.py --stats
"""

import argparse
import json
from orchestrator.database import (
    load_all_runs, load_run_by_id, get_db_stats, reset_database
)


def main():
    parser = argparse.ArgumentParser(description="View Local AI Orchestrator run history")
    parser.add_argument("--run-id", type=int, help="Show details for a specific run ID")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    parser.add_argument("--reset", action="store_true",
                        help="⚠️ Delete ALL run history from the database")
    parser.add_argument("--limit", type=int, default=20,
                        help="Number of recent runs to show (default: 20)")
    args = parser.parse_args()

    if args.reset:
        confirm = input("⚠️  This will delete ALL run history. Type 'yes' to confirm: ")
        if confirm.strip().lower() == "yes":
            reset_database()
            print("Database reset. All run history deleted.")
        else:
            print("Reset cancelled.")
        return

    if args.stats:
        stats = get_db_stats()
        print(f"\nDatabase statistics:")
        print(f"  Total runs   : {stats['total_runs']}")
        print(f"  Passed runs  : {stats['passed_runs']}")
        print(f"  Average score: {stats['average_score']}/100")
        return

    if args.run_id:
        run = load_run_by_id(args.run_id)
        if run is None:
            print(f"No run found with ID {args.run_id}")
            return
        print(f"\n{'='*60}")
        print(f"  Run #{run['id']} — {run['timestamp']}")
        print(f"{'='*60}")
        print(f"  Goal         : {run['goal']}")
        print(f"  Refined goal : {run['refined_goal']}")
        print(f"  Mode         : {run['mode']}")
        print(f"  Model (main) : {run['model_main']}")
        print(f"  Final score  : {run['final_score']}/100")
        print(f"  Passed       : {'Yes' if run['passed'] else 'No'}")
        print(f"  Stop reason  : {run['stop_reason']}")
        print(f"  Scores       : {run['scores_list']}")
        print(f"  Run dir      : {run['run_dir']}")
        print()
        for it in run.get("iterations_detail", []):
            print(f"  --- Iteration {it['iteration']} (score: {it['score']}/100) ---")
            print(f"  Critique preview: {it['critique'][:200]}...")
            print()
        print("FINAL OUTPUT:")
        print(run.get("final_output", "[not stored]"))
        return

    # Default: show recent runs as a table
    runs = load_all_runs(limit=args.limit)
    if not runs:
        print("\nNo runs found in the database yet.")
        print("Run the pipeline with: python run.py --goal '...'")
        return

    print(f"\n{'ID':<5} {'Timestamp':<20} {'Score':<8} {'Pass':<6} "
          f"{'Loops':<6} {'Mode':<10} Goal")
    print("-" * 80)
    for r in runs:
        goal_preview = r["goal"][:35] + ("..." if len(r["goal"]) > 35 else "")
        passed_str = "✓" if r["passed"] else "✗"
        print(
            f"{r['id']:<5} {r['timestamp'][:19]:<20} "
            f"{r['final_score']:<8} {passed_str:<6} "
            f"{r['iterations']:<6} {r['mode']:<10} {goal_preview}"
        )
    print()
    print(f"  Showing {len(runs)} most recent runs.")
    print(f"  Use --run-id <ID> to see full details for a specific run.")


if __name__ == "__main__":
    main()
```

Save the file.

Test it after a pipeline run:
```bash
python show_history.py
python show_history.py --stats
python show_history.py --run-id 1
```

---

## 14.6 Add run history to the Streamlit dashboard

Open `app/streamlit_app.py` and add the following at the bottom of the file,
after the existing `if run_btn:` block:

```python
# ── Run history panel ─────────────────────────────────────────────────────────

st.divider()
st.subheader("🗂️ Run History")

from orchestrator.database import load_all_runs, load_run_by_id, get_db_stats

stats = get_db_stats()
col_s1, col_s2, col_s3 = st.columns(3)
col_s1.metric("Total runs", stats["total_runs"])
col_s2.metric("Passed", stats["passed_runs"])
col_s3.metric("Avg score", f"{stats['average_score']}/100")

runs = load_all_runs(limit=30)

if not runs:
    st.info("No runs yet. Run the pipeline above to see history here.")
else:
    selected_id = st.selectbox(
        "Select a past run to view",
        options=[r["id"] for r in runs],
        format_func=lambda rid: next(
            f"#{r['id']} — {r['timestamp'][:16]} — "
            f"{r['goal'][:50]}{'...' if len(r['goal']) > 50 else ''} "
            f"[{r['final_score']}/100]"
            for r in runs if r["id"] == rid
        ),
    )

    if selected_id:
        past_run = load_run_by_id(selected_id)
        if past_run:
            with st.expander(f"Run #{past_run['id']} details", expanded=True):
                st.markdown(f"**Goal:** {past_run['goal']}")
                st.markdown(f"**Mode:** {past_run['mode']} · "
                            f"**Score:** {past_run['final_score']}/100 · "
                            f"**Passed:** {'Yes ✓' if past_run['passed'] else 'No ✗'}")
                st.markdown(f"**Stop reason:** {past_run['stop_reason']}")

                if past_run.get("scores_list"):
                    st.line_chart({"Score": past_run["scores_list"]},
                                  height=150, use_container_width=True)

                st.markdown("**Final output:**")
                st.markdown(past_run.get("final_output", "_Not stored_"))
```

---

## 14.7 How to back up the database

The database file lives at `runs/history.db`. To back it up:
```bash
cp runs/history.db runs/history_backup_$(date +%Y%m%d).db
```
**What this does:** Copies the database file to a timestamped backup name in the
same `runs/` folder.

For a more thorough backup that is safe even if a write is in progress:
```bash
sqlite3 runs/history.db ".backup runs/history_backup_$(date +%Y%m%d).db"
```
**What this does:** Uses SQLite's built-in backup API to create a consistent snapshot
even if the database is open. Requires `sqlite3` CLI (included in macOS).

---

## 14.8 How to reset the database

⚠️ **This deletes all run history permanently.**

```bash
python show_history.py --reset
```

You will be prompted to type `yes` to confirm. Alternatively, just delete the file:
```bash
rm runs/history.db
```
The next pipeline run will recreate it automatically.

---

## 14.9 What files should and should not be committed to GitHub

**Commit these:**
```
agents/
orchestrator/graph.py
orchestrator/state.py
orchestrator/database.py    ← the schema code, not the data
app/streamlit_app.py
run.py
run_langgraph.py
run_phase2.py
run_phase3.py
show_history.py
prompts/*.txt
config/models.yaml
config/modes.yaml
requirements.txt
requirements-lock.txt
activate.sh
.gitignore
README.md
```

**Do NOT commit these:**
```
.venv/               ← virtual environment (thousands of files)
runs/                ← generated output (large text, personal data)
logs/                ← debug logs
runs/history.db      ← your personal run history
*.pyc                ← compiled Python bytecode
.DS_Store            ← macOS metadata
.env                 ← environment variables (may contain secrets)
```

All of the "do not commit" items are already covered by the `.gitignore` you
created in Section 7.9. Verify before pushing:
```bash
git status
```
If you see any of the above files listed as "untracked" or "modified", something
is wrong with your `.gitignore`. Do not commit them.

---

# SECTION 15 — Workflow Modes

Workflow modes let the pipeline adapt its prompts and scoring rubric to the type
of task. A coding task should be judged on correctness and runnability. A writing
task should be judged on clarity and completeness. A planning task should produce
structured, actionable steps.

---

## 15.1 The six modes

| Mode | Best for |
|------|----------|
| `writing` | Essays, blog posts, explanations, documentation, creative writing |
| `coding` | Python scripts, functions, classes, CLI tools |
| `planning` | Roadmaps, project plans, decision frameworks, strategy |
| `debugging` | Diagnosing errors in existing code or reasoning |
| `study` | Concept explanations, learning guides, summaries, Q&A |
| `general` | Mixed tasks, or when mode is unclear |

---

## 15.2 Write `config/modes.yaml`

This file defines what changes per mode. The pipeline code reads it to select
the right prompt suffix and scoring weights.

```bash
code config/modes.yaml
```

```yaml
# modes.yaml
# Defines how each workflow mode modifies the pipeline behavior.
# The 'prompt_suffix' is appended to the Builder and Fixer system prompts.
# The 'scoring_weights' override the Judge's default equal weighting.
# The 'output_format' tells agents what the final deliverable should look like.

modes:

  writing:
    description: "Essays, blog posts, explanations, and documentation"
    output_format: "Prose with clear sections and a conclusion. Well-structured paragraphs."
    prompt_suffix: |
      This is a WRITING task. Prioritize:
      - Clear, engaging prose
      - Logical structure with an introduction, body, and conclusion
      - Concrete examples that illustrate abstract points
      - Active voice and varied sentence length
      Avoid bullet-point-only responses. Write in full paragraphs.
    scoring_weights:
      completeness: 25
      accuracy: 20
      clarity: 30
      usefulness: 25
    judge_note: "Pay extra attention to prose quality and argument flow."

  coding:
    description: "Writing new Python code, functions, scripts, or programs"
    output_format: "Runnable Python code with inline comments. Include example usage."
    prompt_suffix: |
      This is a CODING task. The output must be:
      - Runnable Python code
      - Syntactically correct
      - Includes at minimum one usage example (as a __main__ block or doctest)
      - Includes brief inline comments explaining non-obvious logic
      - Uses clear variable and function names
      Do not write pseudocode unless explicitly asked. Write real, runnable code.
    scoring_weights:
      completeness: 20
      accuracy: 35
      clarity: 20
      usefulness: 25
    judge_note: |
      For coding tasks: accuracy means the code is syntactically correct and
      logically sound. Broken or non-runnable code must be scored 0 for accuracy
      and must be listed as a hard fail.

  planning:
    description: "Project plans, roadmaps, decision frameworks, and strategy"
    output_format: "Structured plan with numbered phases, tasks, owners, and success criteria."
    prompt_suffix: |
      This is a PLANNING task. The output must be:
      - A structured, numbered plan
      - Each phase or step includes: what, why, and success criteria
      - Realistic and actionable — avoid vague recommendations
      - Ordered logically (dependencies considered)
      Avoid writing lengthy prose. Use structured lists, tables, or numbered steps.
    scoring_weights:
      completeness: 30
      accuracy: 20
      clarity: 25
      usefulness: 25
    judge_note: "Judge the plan on whether someone could actually follow it."

  debugging:
    description: "Diagnosing and fixing errors in existing code or reasoning"
    output_format: "Numbered hypotheses, root cause analysis, and a concrete fix."
    prompt_suffix: |
      This is a DEBUGGING task. Structure the response as:
      1. Restate the problem clearly
      2. List likely root causes in order of probability
      3. Explain diagnostic steps for each hypothesis
      4. Provide the recommended fix with exact code changes
      5. Explain how to verify the fix worked
      Be concrete. Do not suggest "it might be X" without explaining how to check.
    scoring_weights:
      completeness: 20
      accuracy: 40
      clarity: 20
      usefulness: 20
    judge_note: |
      For debugging: accuracy is the dominant criterion. An elegant but wrong
      diagnosis is worse than a plain but correct one. A fix that does not
      actually resolve the described problem must score 0 for accuracy.

  study:
    description: "Concept explanations, learning guides, and summaries"
    output_format: "Explanation that builds from simple to complex, with analogies and examples."
    prompt_suffix: |
      This is a STUDY/EXPLANATION task. Write for someone who is smart and
      motivated but unfamiliar with this specific topic. Structure the explanation:
      1. Start with the simplest possible summary (one sentence)
      2. Build to a fuller explanation step by step
      3. Use at least one concrete analogy
      4. Include at least one practical example
      5. End with what the reader should understand now and what to learn next
      Avoid assuming prior knowledge of domain-specific terms without defining them.
    scoring_weights:
      completeness: 25
      accuracy: 25
      clarity: 30
      usefulness: 20
    judge_note: "Judge whether a smart beginner would actually understand this."

  general:
    description: "Mixed tasks or unclear goal type"
    output_format: "Whatever format best serves the goal."
    prompt_suffix: |
      Respond in whatever format best serves the goal.
      Be thorough, accurate, and clear. Structure the response logically.
    scoring_weights:
      completeness: 25
      accuracy: 25
      clarity: 25
      usefulness: 25
    judge_note: "Apply balanced judgment across all four rubric categories."
```

Save the file.

---

## 15.3 Write the mode loader

**File path:** `orchestrator/modes.py`

```bash
code orchestrator/modes.py
```

```python
"""
orchestrator/modes.py

Loads workflow mode configuration from config/modes.yaml.
Provides helpers to get the prompt suffix, scoring weights, and judge note
for a given mode.
"""

from pathlib import Path
import yaml


_MODES_PATH = Path("config") / "modes.yaml"
_modes_cache: dict | None = None


def _load_modes() -> dict:
    global _modes_cache
    if _modes_cache is None:
        with open(_MODES_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        _modes_cache = data.get("modes", {})
    return _modes_cache


def get_mode_config(mode: str) -> dict:
    """
    Return the full config dict for a given mode.
    Falls back to 'general' if the mode is not recognised.
    """
    modes = _load_modes()
    return modes.get(mode, modes.get("general", {}))


def get_prompt_suffix(mode: str) -> str:
    """Return the prompt suffix string for a given mode."""
    return get_mode_config(mode).get("prompt_suffix", "").strip()


def get_scoring_weights(mode: str) -> dict:
    """
    Return the scoring weights dict for a given mode.
    Keys: completeness, accuracy, clarity, usefulness (each 0–25 by default).
    """
    return get_mode_config(mode).get("scoring_weights", {
        "completeness": 25,
        "accuracy": 25,
        "clarity": 25,
        "usefulness": 25,
    })


def get_judge_note(mode: str) -> str:
    """Return the extra judge instruction for a given mode."""
    return get_mode_config(mode).get("judge_note", "").strip()


def get_output_format(mode: str) -> str:
    """Return the expected output format description for a given mode."""
    return get_mode_config(mode).get("output_format", "").strip()


def list_modes() -> list[str]:
    """Return all available mode names."""
    return list(_load_modes().keys())
```

Save the file.

---

## 15.4 Wire modes into the agent prompts

Update `agents/builder.py` to inject the mode's prompt suffix. Replace the
`run()` method body with:

```python
    def run(self, goal: str, plan: str, mode: str = "general") -> str:
        from orchestrator.modes import get_prompt_suffix, get_output_format
        system_prompt = self.load_prompt_template()
        suffix = get_prompt_suffix(mode)
        output_format = get_output_format(mode)

        full_prompt = f"""{system_prompt}

{suffix}

EXPECTED OUTPUT FORMAT:
{output_format}

USER GOAL:
{goal}

PLAN TO FOLLOW:
{plan}

Now write the complete deliverable according to the plan above.
"""
        print(f"  [Builder] Calling {self.model} (mode: {mode})...")
        result = self.call_model(full_prompt)
        print(f"  [Builder] Draft complete ({len(result)} chars)")
        return result
```

Update `agents/fixer.py` `run()` method similarly — add `mode: str = "general"`
parameter and inject `get_prompt_suffix(mode)` at the top of `full_prompt`.

Update `agents/judge.py` `run()` method to inject the mode's judge note and
scoring weights. Add `mode: str = "general"` parameter:

```python
    def run(self, goal: str, draft: str, iteration: int = 1,
            mode: str = "general") -> dict:
        from orchestrator.modes import get_judge_note, get_scoring_weights
        system_prompt = self.load_prompt_template()
        judge_note = get_judge_note(mode)
        weights = get_scoring_weights(mode)

        full_prompt = f"""{system_prompt}

MODE-SPECIFIC INSTRUCTION:
{judge_note}

SCORING WEIGHTS FOR THIS MODE:
- completeness : {weights['completeness']} points max
- accuracy     : {weights['accuracy']} points max
- clarity      : {weights['clarity']} points max
- usefulness   : {weights['usefulness']} points max
Total: 100 points

ORIGINAL GOAL:
{goal}

DRAFT TO SCORE (iteration {iteration}):
{draft}

Return ONLY the JSON object. No explanation, no markdown, no code fences.
"""
        # rest of method unchanged ...
```

Pass `mode` through from the pipeline caller in `run.py` and `run_langgraph.py`.

---

## 15.5 Per-mode output expectations

### Writing mode
- Output: full prose — introduction, body paragraphs, conclusion.
- What it should NOT do: return a bullet list when the goal asks for an essay;
  truncate mid-section; add "I hope this helps" or similar filler.

### Coding mode
- Output: syntactically valid Python. A `if __name__ == "__main__":` block
  showing usage. Inline comments on non-obvious logic.
- What it should NOT do: return pseudocode as the final answer; omit imports;
  produce code that raises a `SyntaxError`.

### Planning mode
- Output: numbered phases with sub-tasks, success criteria, and realistic
  time estimates if relevant.
- What it should NOT do: write a vague strategy essay without concrete steps;
  confuse phases with tasks; ignore dependencies.

### Debugging mode
- Output: ranked hypotheses → diagnostic steps → exact fix → verification.
- What it should NOT do: give a generic "check your imports" answer; suggest
  fixes without explaining why they would work; skip the verification step.

### Study mode
- Output: layered explanation — one-sentence summary → fuller explanation →
  analogy → example → next steps.
- What it should NOT do: assume the reader knows domain vocabulary; produce
  a Wikipedia-style encyclopedic entry without a learning arc; omit examples.

### General mode
- Output: whatever format best serves the goal.
- What it should NOT do: override the user's explicit formatting requests.

---

## 15.6 How to test each mode

```bash
# Writing mode
python run.py \
    --goal "Write a 500-word blog post about why sleep matters for developers." \
    --max-loops 2 --threshold 65

# Planning mode
python run.py \
    --goal "Create a 4-week learning plan for someone who wants to learn FastAPI." \
    --max-loops 2 --threshold 65

# Coding mode
python run.py \
    --goal "Write a Python function that reads a CSV file and returns the top 5 rows by a given column." \
    --max-loops 2 --threshold 65

# Study mode
python run.py \
    --goal "Explain what a Python decorator is and how to write one from scratch." \
    --max-loops 2 --threshold 65

# Debugging mode
python run.py \
    --goal "My Python script raises KeyError: 'name' when parsing JSON from an API. Diagnose and fix." \
    --max-loops 2 --threshold 65
```

After each run, check that:
- The output format matches the mode description.
- The Judge scores align with the mode weights (e.g., coding mode should show
  `accuracy` as the highest-weighted category).
- The saved `run_summary.json` correctly records the mode.

---

## 15.7 Adding modes later

To add a new mode (e.g., `research` or `summarization`):

1. Add a new entry to `config/modes.yaml` following the existing format.
2. No Python code changes needed — `get_mode_config()` reads any key from the file.
3. Add the mode name to the Streamlit sidebar `selectbox` options list in
   `app/streamlit_app.py`.
4. Add a test case in `tests/`.

---

*End of Sections 14 and 15.*

---

> **Next sections to write:** Section 16 (Coding Verification) and
> Section 17 (Prompt Templates).

---

# SECTION 16 — Coding Verification

For coding tasks, you do not want the pipeline to pass a draft just because the
Judge model *thinks* the code is correct. Models hallucinate working code. The only
way to know if Python code runs is to actually run it. This section adds real
execution-based verification that feeds results back into the critique loop.

---

## 16.1 The verification strategy

When mode is `coding`, the pipeline does the following **after the Fixer produces
a revised draft** and **before the Judge scores it**:

1. Extract the Python code block from the draft.
2. Write it to a temporary file.
3. Run `python <tempfile>` in a subprocess with a timeout.
4. Capture stdout, stderr, and return code.
5. If the code errors (non-zero return code), inject the error log into the
   critique that the Fixer will receive in the next iteration.
6. Force the Judge to record `"broken_code"` as a hard fail if errors occurred.
7. Never let broken code pass the quality threshold regardless of other scores.

---

## 16.2 Safety concerns before you run generated code

**Read this before enabling code execution.**

Running AI-generated code on your machine carries real risk. The model could
generate code that:
- Deletes files (`os.remove`, `shutil.rmtree`).
- Makes network requests to external servers.
- Installs packages (`subprocess.run(["pip", "install", ...])`).
- Reads sensitive files from your home directory.
- Runs infinite loops that hang the subprocess.

**Mitigations used in this implementation:**
- All code runs with a strict **timeout** (default 10 seconds). Any code that
  hangs is killed.
- Code runs as your user account with no privilege escalation.
- The temporary file is written to `/tmp/` (isolated from your project).
- The code runner captures output but does not stream it to the main process.
- Dangerous imports are detected and blocked before execution (see 16.4).

**What this does NOT protect against:**
- Code that reads and exfiltrates files within your user account.
- Code that makes HTTP requests (blocked by a blocklist, not a sandbox).
- Code that uses subprocesses to escape the timeout.

For a fully safe sandbox you would use Docker or a restricted execution
environment. That is outside the scope of this MVP. For now, treat the code
runner as a **developer tool on your own machine**, not a production sandbox.
Only run the pipeline on code tasks you would be comfortable running yourself.

---

## 16.3 Write the code runner module

**File path:** `orchestrator/code_runner.py`

```bash
code orchestrator/code_runner.py
```

```python
"""
orchestrator/code_runner.py

Extracts Python code from agent output and runs it in a subprocess.
Returns execution results (stdout, stderr, return code) for use in
the critique/fix loop.

Safety note: This runs generated code on your local machine.
Only use in coding mode on tasks you trust. See Section 16.2 of the
build guide for a full safety discussion.
"""

import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


# Timeout in seconds for code execution
EXECUTION_TIMEOUT = 15

# Imports that should never be allowed to execute
BLOCKED_PATTERNS = [
    r"\bos\.remove\b",
    r"\bshutil\.rmtree\b",
    r"\bshutil\.rmdir\b",
    r"\bos\.rmdir\b",
    r"\bsubprocess\.(?:run|call|Popen|check_output)\b.*shell\s*=\s*True",
    r"__import__\s*\(\s*['\"]os['\"]\s*\)",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"open\s*\(.*['\"]w['\"].*\).*(?:home|Documents|Desktop|Downloads)",
]


class CodeRunResult:
    """Result of a code execution attempt."""

    def __init__(self, success: bool, stdout: str, stderr: str,
                 returncode: int, blocked: bool = False,
                 blocked_reason: str = ""):
        self.success = success          # True if returncode == 0
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.blocked = blocked          # True if blocked before execution
        self.blocked_reason = blocked_reason

    def as_feedback(self) -> str:
        """
        Format the result as feedback text for the Fixer/Critic to consume.
        """
        if self.blocked:
            return (
                f"CODE EXECUTION BLOCKED\n"
                f"Reason: {self.blocked_reason}\n"
                f"The code was not executed. Remove the flagged pattern and rewrite."
            )
        if self.success:
            out = self.stdout[:1000] if self.stdout else "(no output)"
            return f"CODE EXECUTED SUCCESSFULLY\nOutput:\n{out}"
        else:
            err = self.stderr[:2000] if self.stderr else "(no error output captured)"
            out = self.stdout[:500] if self.stdout else ""
            feedback = f"CODE EXECUTION FAILED (exit code {self.returncode})\n"
            if out:
                feedback += f"Stdout before failure:\n{out}\n\n"
            feedback += f"Error output:\n{err}"
            return feedback

    @property
    def is_hard_fail(self) -> bool:
        """True if this result must be reported as a hard fail to the Judge."""
        return self.blocked or not self.success


def extract_python_code(text: str) -> str | None:
    """
    Extract Python code from a model response.

    Tries in order:
    1. ```python ... ``` fenced block
    2. ``` ... ``` fenced block (no language tag)
    3. The full text if it looks like bare Python (starts with import/def/class)
    Returns None if no code block is found.
    """
    # Try fenced python block
    match = re.search(r"```python\s*([\s\S]*?)```", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Try any fenced block
    match = re.search(r"```\s*([\s\S]*?)```", text)
    if match:
        code = match.group(1).strip()
        # Quick sanity check: does it look like Python?
        if any(code.startswith(kw) for kw in
               ("import ", "from ", "def ", "class ", "#")):
            return code

    # Try bare Python (no fences)
    stripped = text.strip()
    if any(stripped.startswith(kw) for kw in
           ("import ", "from ", "def ", "class ", "#!")):
        return stripped

    return None


def check_for_blocked_patterns(code: str) -> tuple[bool, str]:
    """
    Check for dangerous patterns before execution.
    Returns (is_blocked, reason).
    """
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, code, re.IGNORECASE):
            return True, f"Matched blocked pattern: {pattern}"
    return False, ""


def run_python_code(code: str, timeout: int = EXECUTION_TIMEOUT) -> CodeRunResult:
    """
    Write code to a temp file and execute it.
    Returns a CodeRunResult with stdout, stderr, and success status.
    """
    # Safety check first
    blocked, reason = check_for_blocked_patterns(code)
    if blocked:
        return CodeRunResult(
            success=False, stdout="", stderr="",
            returncode=-1, blocked=True, blocked_reason=reason
        )

    # Write to a temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", prefix="orchtest_",
        dir="/tmp", delete=False, encoding="utf-8"
    ) as f:
        f.write(code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return CodeRunResult(
            success=(result.returncode == 0),
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
        )
    except subprocess.TimeoutExpired:
        return CodeRunResult(
            success=False,
            stdout="",
            stderr=f"Execution timed out after {timeout} seconds.",
            returncode=-2,
        )
    except Exception as exc:
        return CodeRunResult(
            success=False,
            stdout="",
            stderr=f"Runner error: {exc}",
            returncode=-3,
        )
    finally:
        # Always clean up the temp file
        Path(tmp_path).unlink(missing_ok=True)


def verify_draft_code(draft: str, timeout: int = EXECUTION_TIMEOUT) -> CodeRunResult:
    """
    High-level entry point: extract code from a draft and run it.
    If no code block is found, returns a result indicating no code to run.
    """
    code = extract_python_code(draft)
    if code is None:
        return CodeRunResult(
            success=False,
            stdout="",
            stderr="No Python code block found in the draft.",
            returncode=-4,
        )
    return run_python_code(code, timeout=timeout)
```

Save the file.

---

## 16.4 Wire code verification into the pipeline loop

In `run.py`, inside the improvement loop, add a verification step between
the Fixer and the Judge. Locate this block:

```python
        # Judge
        verdict = judge.run(goal=refined_goal, draft=revised, iteration=iteration)
```

Replace it with:

```python
        # ── Code verification (coding mode only) ─────────────────────────────
        code_feedback = ""
        if mode == "coding":
            from orchestrator.code_runner import verify_draft_code
            print(f"  [Verifier] Running generated code (iteration {iteration})...")
            run_result = verify_draft_code(revised)
            code_feedback = run_result.as_feedback()
            save(run_dir, f"loop{iteration:02d}_code_run.txt", code_feedback)
            if run_result.success:
                print(f"  [Verifier] ✓ Code ran successfully")
            else:
                print(f"  [Verifier] ✗ Code failed — injecting error into critique")
                # Append error to critique so Fixer sees it in next iteration
                critique = critique + f"\n\nCODE EXECUTION RESULT:\n{code_feedback}"
                save(run_dir, f"loop{iteration:02d}_critic.txt", critique)

        # Judge
        verdict = judge.run(
            goal=refined_goal, draft=revised,
            iteration=iteration, mode=mode
        )

        # Force hard fail if code is broken
        if mode == "coding" and code_feedback:
            from orchestrator.code_runner import verify_draft_code
            if "FAILED" in code_feedback or "BLOCKED" in code_feedback:
                if "broken_code" not in verdict.get("hard_fails", []):
                    verdict["hard_fails"].append("broken_code")
                verdict["pass"] = False
                print(f"  [Judge] Hard fail: broken code overrides score")
```

---

## 16.5 Write the pytest integration

For coding tasks where the goal explicitly asks for testable code, the pipeline
can run `pytest` on the generated code instead of (or in addition to) running
it directly.

**File path:** `orchestrator/pytest_runner.py`

```bash
code orchestrator/pytest_runner.py
```

```python
"""
orchestrator/pytest_runner.py

Runs pytest on generated Python code and returns structured results.
Used in coding mode when the generated code includes test functions.
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path


def has_test_functions(code: str) -> bool:
    """Return True if the code contains pytest-compatible test functions."""
    return bool(re.search(r"^def test_", code, re.MULTILINE))


def run_pytest_on_code(code: str, timeout: int = 30) -> dict:
    """
    Write code to a temp file and run pytest on it.

    Returns a dict:
        passed: bool
        num_passed: int
        num_failed: int
        num_errors: int
        output: str (pytest stdout/stderr)
        hard_fail: bool
    """
    if not has_test_functions(code):
        return {
            "passed": None,     # None = no tests found, not a failure
            "num_passed": 0,
            "num_failed": 0,
            "num_errors": 0,
            "output": "No test functions found in the generated code.",
            "hard_fail": False,
        }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix="_test.py", prefix="orchpytest_",
        dir="/tmp", delete=False, encoding="utf-8"
    ) as f:
        f.write(code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", tmp_path, "-v",
             "--tb=short", "--no-header", "-q"],
            capture_output=True, text=True, timeout=timeout,
        )
        output = result.stdout + result.stderr

        # Parse summary line: "3 passed, 1 failed, 0 errors"
        num_passed = len(re.findall(r"PASSED", output))
        num_failed = len(re.findall(r"FAILED", output))
        num_errors = len(re.findall(r"ERROR", output))

        passed = (result.returncode == 0)
        return {
            "passed": passed,
            "num_passed": num_passed,
            "num_failed": num_failed,
            "num_errors": num_errors,
            "output": output[:3000],
            "hard_fail": not passed,
        }
    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "num_passed": 0,
            "num_failed": 0,
            "num_errors": 1,
            "output": f"pytest timed out after {timeout} seconds.",
            "hard_fail": True,
        }
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def pytest_result_as_feedback(result: dict) -> str:
    """Format pytest results as feedback for the Fixer agent."""
    if result["passed"] is None:
        return "No test functions were found. Add pytest test functions (def test_*) to verify the code."
    if result["passed"]:
        return (
            f"PYTEST PASSED: {result['num_passed']} test(s) passed.\n"
            f"Output:\n{result['output']}"
        )
    return (
        f"PYTEST FAILED: {result['num_passed']} passed, "
        f"{result['num_failed']} failed, {result['num_errors']} errors.\n"
        f"Full output:\n{result['output']}"
    )
```

Save the file.

---

## 16.6 Add linting with `ruff`

Linting catches style and common error patterns before execution. `ruff` is a
fast Python linter written in Rust that replaces flake8/pylint for most purposes.

Install it:
```bash
pip install ruff
```

Add to `requirements.txt`:
```
ruff>=0.4.0
```

**File path:** `orchestrator/linter.py`

```bash
code orchestrator/linter.py
```

```python
"""
orchestrator/linter.py

Runs ruff linting on generated Python code.
Linting runs before code execution so fixable issues are surfaced early.
"""

import subprocess
import sys
import tempfile
from pathlib import Path


def lint_python_code(code: str) -> dict:
    """
    Run ruff on the provided Python code string.

    Returns:
        clean: bool — True if no lint errors found
        issues: list of issue strings
        output: full ruff stdout
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", prefix="orchlint_",
        dir="/tmp", delete=False, encoding="utf-8"
    ) as f:
        f.write(code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", tmp_path,
             "--output-format=text", "--no-cache"],
            capture_output=True, text=True, timeout=15,
        )
        output = result.stdout.strip()
        issues = [line for line in output.splitlines()
                  if line and not line.startswith("Found")]
        return {
            "clean": result.returncode == 0,
            "issues": issues,
            "output": output[:2000],
        }
    except FileNotFoundError:
        return {
            "clean": True,
            "issues": [],
            "output": "ruff not installed — skipping lint check",
        }
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def lint_result_as_feedback(result: dict) -> str:
    if result["clean"]:
        return "LINT: No issues found."
    issue_list = "\n".join(f"  - {i}" for i in result["issues"][:20])
    return f"LINT ISSUES FOUND ({len(result['issues'])} total):\n{issue_list}"
```

Save the file.

---

## 16.7 Combined verification function

Add a convenience function that runs lint → exec → pytest in sequence and
returns combined feedback:

**File path:** `orchestrator/verifier.py`

```bash
code orchestrator/verifier.py
```

```python
"""
orchestrator/verifier.py

Combined verification for coding mode:
  1. Extract Python code from draft
  2. Lint with ruff
  3. Execute with subprocess
  4. Run pytest if test functions are present

Returns combined feedback text and hard_fail flag.
"""

from orchestrator.code_runner import extract_python_code, run_python_code
from orchestrator.linter import lint_python_code, lint_result_as_feedback
from orchestrator.pytest_runner import (
    run_pytest_on_code, pytest_result_as_feedback
)


def verify_coding_draft(draft: str) -> dict:
    """
    Run full verification pipeline on a coding draft.

    Returns:
        feedback: str  — combined feedback for Fixer/Critic
        hard_fail: bool — True if code should not be allowed to pass
        details: dict  — individual results from each verification step
    """
    code = extract_python_code(draft)
    if code is None:
        return {
            "feedback": (
                "VERIFICATION FAILED: No Python code block found in the draft.\n"
                "The draft must contain a fenced ```python ... ``` code block."
            ),
            "hard_fail": True,
            "details": {"no_code": True},
        }

    feedback_parts = []
    hard_fail = False
    details = {}

    # Step 1: Lint
    lint_result = lint_python_code(code)
    details["lint"] = lint_result
    lint_feedback = lint_result_as_feedback(lint_result)
    feedback_parts.append(lint_feedback)
    # Lint issues are warnings, not hard fails (unless there are many)
    if len(lint_result["issues"]) > 10:
        hard_fail = True
        feedback_parts.append(
            "Too many lint issues (>10). Fix fundamental style/syntax problems first."
        )

    # Step 2: Execute
    run_result = run_python_code(code)
    details["execution"] = {
        "success": run_result.success,
        "returncode": run_result.returncode,
        "stdout": run_result.stdout[:500],
        "stderr": run_result.stderr[:1000],
    }
    exec_feedback = run_result.as_feedback()
    feedback_parts.append(exec_feedback)
    if run_result.is_hard_fail:
        hard_fail = True

    # Step 3: pytest (only if execution succeeded and tests exist)
    if run_result.success:
        pytest_result = run_pytest_on_code(code)
        details["pytest"] = pytest_result
        pytest_feedback = pytest_result_as_feedback(pytest_result)
        feedback_parts.append(pytest_feedback)
        if pytest_result.get("hard_fail"):
            hard_fail = True

    combined_feedback = "\n\n".join(feedback_parts)
    return {
        "feedback": combined_feedback,
        "hard_fail": hard_fail,
        "details": details,
    }
```

Save the file.

---

## 16.8 Example: a coding pipeline run

```bash
python run.py \
    --goal "Write a Python function called word_count(text: str) -> dict that counts word frequencies in a string, ignoring case and punctuation. Include at least 3 pytest test functions." \
    --max-loops 3 \
    --threshold 70
```

**What happens:**
1. Supervisor detects `coding` mode.
2. Builder writes a Python function with test functions.
3. Critic reviews the draft.
4. Fixer revises it.
5. Verifier runs lint → exec → pytest on the revised code.
6. If pytest fails, the error log is appended to the critique for the next loop.
7. Judge scores the result with `accuracy` weighted at 35/100.
8. If code is broken, `hard_fail: ["broken_code"]` prevents passing.

**Example saved files for a 2-loop coding run:**
```
runs/20240115_160000/
├── 00_supervisor.json
├── 01_planner_plan.txt
├── 02_builder_draft_v0.txt
├── loop01_critic.txt
├── loop01_fixer.txt
├── loop01_code_run.txt       ← "CODE EXECUTION FAILED: NameError..."
├── loop01_judge.json         ← hard_fail: ["broken_code"], pass: false
├── loop02_critic.txt         ← includes the error log from loop01
├── loop02_fixer.txt          ← revised with bug fixed
├── loop02_code_run.txt       ← "CODE EXECUTED SUCCESSFULLY"
├── loop02_judge.json         ← score 79, pass: true
├── best_draft.txt
├── final_output.txt
└── run_summary.json
```

---

## 16.9 Phase 16 success criteria

- [ ] `verify_coding_draft()` correctly extracts Python code from a fenced block.
- [ ] A draft with a `SyntaxError` returns `hard_fail: True` and a useful error msg.
- [ ] A draft with correct code returns `success: True` and stdout.
- [ ] Blocked patterns (e.g. `os.remove`) are caught before execution.
- [ ] A draft with failing pytest tests returns `hard_fail: True` with test output.
- [ ] The Judge never passes a draft with `hard_fail: ["broken_code"]`.
- [ ] The Fixer receives the execution error in its critique on the next iteration.

---

# SECTION 17 — Prompt Templates

These are the production-quality, final prompt templates for all seven agents.
They replace the minimal templates you created in earlier sections. Each one is
in its own file under `prompts/`.

Copy each block below exactly into its corresponding file.

---

## 17.1 Supervisor — `prompts/supervisor.txt`

```bash
code prompts/supervisor.txt
```

```
You are the Supervisor agent in a high-quality multi-agent AI pipeline.

YOUR ROLE:
You are the first agent in the pipeline. You receive the user's raw goal and
perform two jobs:
1. Rewrite the goal as a single, unambiguous, actionable problem statement.
2. Determine which workflow mode best fits the task.

MODES AVAILABLE:
- writing   : essays, blog posts, documentation, creative or technical prose
- coding    : writing new Python code, functions, scripts, or programs
- planning  : roadmaps, project plans, decision frameworks, timelines, strategy
- debugging : diagnosing and fixing errors in existing code or reasoning
- study     : explaining concepts, learning guides, step-by-step tutorials
- general   : mixed tasks, unclear type, or anything that doesn't fit above

HOW TO REWRITE THE GOAL:
- If the goal is clear and specific, keep it close to the original.
- If it is vague ("help me with Python"), make it specific ("Explain how Python
  list comprehensions work, with three progressively complex examples").
- If it is ambiguous (could be writing or coding), ask yourself: what output would
  satisfy this user? Code? Prose? A plan? Let that answer guide the mode.
- Do not add constraints the user did not state.
- Do not change the intent — only improve the clarity and precision.
- The refined goal should be one paragraph or less.

OUTPUT FORMAT (required — two labeled lines):
REFINED GOAL: <single clear problem statement>
MODE: <one word from the modes list above>

FAILURE MODES TO AVOID:
- Do not return multiple goals or a bulleted list.
- Do not ask the user clarifying questions (proceed with your best interpretation).
- Do not add "I will now..." preamble. Return only the two labeled lines.
- Do not pick a mode that is not in the modes list.
```

---

## 17.2 Planner — `prompts/planner.txt`

```bash
code prompts/planner.txt
```

```
You are the Planner agent in a high-quality multi-agent AI pipeline.

YOUR ROLE:
You receive a clear goal and a workflow mode. You produce a structured,
numbered plan that the Builder agent will follow to create the deliverable.
You are the architect. You do not build anything yet — you design the blueprint.

HOW TO WRITE THE PLAN:
- Write 4–8 numbered steps. Fewer for simple tasks, more for complex ones.
- Each step names a concrete section, component, or action.
- Each step is 1–3 sentences: what it contains and why it matters.
- The plan must be ordered logically. Dependencies come before what depends on them.
- Calibrate to the mode:
    writing   → plan the structure (intro, sections, examples, conclusion)
    coding    → plan the architecture (inputs, outputs, core logic, edge cases, tests)
    planning  → list phases, milestones, risks, success criteria
    debugging → list hypotheses in order of likelihood, then diagnosis steps
    study     → plan the explanation arc (simple → complex → analogy → example)
    general   → whatever structure best serves the goal

WHAT TO AVOID:
- Do not write the actual content (no prose, no code).
- Do not write vague steps like "make it good" or "improve the quality".
- Do not repeat the goal verbatim as a step.
- Do not include more than 8 steps unless the task genuinely requires it.
- Do not add meta-commentary like "Here is my plan:" — just start with Step 1.

OUTPUT FORMAT:
Step 1: [title] — [what this section contains and why]
Step 2: [title] — [what this section contains and why]
... and so on.
```

---

## 17.3 Builder — `prompts/builder.txt`

```bash
code prompts/builder.txt
```

```
You are the Builder agent in a high-quality multi-agent AI pipeline.

YOUR ROLE:
You receive a goal, a mode, and a structured plan. You write the complete,
full deliverable based on that plan. This is the first draft — it will be
reviewed and improved, but it must be substantive and complete from the start.

RULES:
- Write the COMPLETE deliverable. Not a summary, not an outline, not a preview.
- Follow the plan's structure, but use your full expertise for each section.
- Every step in the plan must appear in your output, fully developed.
- Do not skip sections with "this section would cover..." — write the section.
- Do not truncate. If the plan has 6 steps, your output has 6 full sections.

FOR WRITING TASKS:
- Write in full paragraphs. Use headings if the plan calls for sections.
- Be specific. Concrete examples beat abstract claims every time.
- Do not use filler phrases ("It is worth noting that...", "In conclusion...").
- Write as a knowledgeable expert, not a cautious assistant.

FOR CODING TASKS:
- Return the code in a fenced ```python ... ``` block.
- Include all necessary imports at the top.
- Include a brief docstring on each function.
- Include a __main__ block or usage example at the bottom.
- Write code that actually runs — not pseudocode, not placeholders.

FOR PLANNING TASKS:
- Use numbered phases with sub-tasks.
- Include success criteria for each phase.
- Be realistic about timelines and effort.

FOR DEBUGGING TASKS:
- State the most likely root cause first.
- Show exact diagnostic steps.
- Provide the exact fix, not "you might try..."

FOR STUDY TASKS:
- Start simple. Build complexity gradually.
- Include at least one analogy and one concrete example.
- End with what the reader should now understand and what to learn next.

WHAT TO NEVER DO:
- Do not mention that you are an AI.
- Do not add disclaimers, caveats, or hedges about your limitations.
- Do not include meta-commentary ("Here is my draft:", "I hope this helps").
- Do not reference the plan structure in your output ("As outlined in Step 3...").
- Do not produce a response shorter than 300 words unless the task is genuinely brief.
```

---

## 17.4 Critic — `prompts/critic.txt`

```bash
code prompts/critic.txt
```

```
You are the Critic agent in a high-quality multi-agent AI pipeline.

YOUR ROLE:
You review a draft against the original goal and identify every specific,
actionable weakness. You are rigorous, specific, and constructive. You do not
rewrite — you only critique. Your feedback is the fuel that makes the next
revision better.

RULES FOR EVERY CRITIQUE:
- Read the original goal carefully before you read the draft.
- Evaluate the draft against the goal, not against some generic standard.
- Find every significant weakness. A good critique has 3–8 specific issues.
- If you cannot find at least 3 issues, you are not looking hard enough.
- For each issue, you MUST provide:
    Issue: what is wrong, precisely
    Location: where in the draft (section name, paragraph number, or line)
    Fix: exactly what should be done (not "improve this" — say HOW)

TYPES OF ISSUES TO LOOK FOR:
- Missing content: sections the goal asked for that are absent
- Incomplete sections: sections that exist but are too shallow or cut short
- Logic gaps: claims made without evidence or reasoning
- Structural problems: wrong order, missing transitions, poor flow
- Vague language: claims like "it is important" without explaining why
- Wrong format: prose where code was expected, or vice versa
- Factual errors: incorrect statements you can identify with confidence
- Poor examples: examples that do not illustrate the point clearly
- Scope creep: content that was not asked for and distracts from the goal

WHAT A GOOD CRITIQUE LOOKS LIKE:
Issue: The explanation of backpropagation is missing entirely.
Location: Section 3 (Training Process)
Fix: Add a paragraph explaining that backpropagation computes gradients by
     applying the chain rule backward through each layer, updating weights
     proportional to their contribution to the error.

WHAT A BAD CRITIQUE LOOKS LIKE (do not do this):
"The writing could be clearer in some places."
"Consider adding more examples."
"The structure is generally good but could be improved."

END YOUR CRITIQUE WITH:
Overall: [one sentence summarizing the most important thing to fix]

WHAT TO AVOID:
- Do not rewrite the draft or provide corrected text.
- Do not praise sections at length — one word acknowledgement is enough.
- Do not be vague. Every issue must be locatable and fixable.
- Do not list more than 8 issues — prioritize the most important ones.
```

---

## 17.5 Fixer — `prompts/fixer.txt`

```bash
code prompts/fixer.txt
```

```
You are the Fixer agent in a high-quality multi-agent AI pipeline.

YOUR ROLE:
You receive a draft and a structured critique. Your job is to produce a
significantly improved revised version that addresses every issue the Critic
raised. You are a skilled reviser, not a copyeditor. Revision may mean
restructuring, expanding, rewriting entire sections, or replacing examples.

HOW TO APPROACH REVISION:
1. Read the original goal first. Every change must serve that goal.
2. Read the critique carefully. List mentally what needs to change.
3. Work through the draft section by section, addressing each critique point.
4. Do not just patch — if a section is fundamentally weak, rewrite it.
5. Preserve everything that was already working well.

RULES:
- Address EVERY issue the Critic raised. Skipping even one is a failure.
- The revised draft must be complete — not a list of changes, not a diff,
  but the full revised document from start to finish.
- Do not include meta-commentary like "I addressed the following issues..."
  or "As the Critic noted..." — produce the deliverable directly.
- Do not introduce new problems while fixing existing ones.
- Do not shorten the draft to fix it — add what was missing, rewrite what
  was wrong, and keep what was good.
- If you disagree with a critique point, address it anyway. Your job is
  revision, not debate.

FOR CODING TASKS:
- If the code had execution errors, fix the root cause — not just the symptom.
- If tests failed, fix the code logic, not the tests.
- Ensure all imports are present and correct.
- Re-verify your logic mentally before outputting the revised code.

WHAT TO NEVER DO:
- Do not summarize what you changed. Output the full revised draft.
- Do not add "Revised draft:" as a label. Just output the content.
- Do not truncate. The revised draft must be at least as long as the original.
- Do not tell the user what you are about to do. Just do it.
```

---

## 17.6 Judge — `prompts/judge.txt`

```bash
code prompts/judge.txt
```

```
You are the Judge agent in a high-quality multi-agent AI pipeline.

YOUR ROLE:
Score a draft against the original goal using a structured rubric. Return a
single valid JSON object and nothing else. Your scoring must be honest and
calibrated — not generous, not harsh. A score of 70 means "good enough for
most purposes." A score of 90 means "genuinely excellent." A score of 50 means
"incomplete or significantly flawed."

CRITICAL: YOUR ENTIRE RESPONSE MUST BE A SINGLE JSON OBJECT.
- The first character must be {
- The last character must be }
- No text before the JSON. No text after the JSON.
- No markdown code fences. No explanation. No preamble.

SCORING RUBRIC:
Each category is worth 0–25 points. Total is 0–100.

completeness (0–25):
  Does the draft fully address everything the original goal asked for?
  25 = nothing missing, all parts addressed
  18 = minor gaps in one area
  10 = one significant section missing or very thin
  0  = large portions of the goal unaddressed

accuracy (0–25):
  Is the content factually correct, logically sound, and free of errors?
  25 = no errors found
  18 = minor inaccuracies that do not mislead
  10 = at least one notable error
  0  = fundamental errors or misleading content
  NOTE: For coding tasks, accuracy means the code is syntactically valid
  and the logic is correct. Broken code scores 0 and is a hard fail.

clarity (0–25):
  Is the output clear, well-structured, and easy to follow?
  25 = excellent structure and flow, no confusing parts
  18 = mostly clear with minor rough spots
  10 = several confusing or poorly structured sections
  0  = difficult to follow throughout

usefulness (0–25):
  Would the target audience find this immediately useful and actionable?
  25 = directly meets the need, could be used as-is
  18 = useful but minor adjustments needed
  10 = has value but significant gaps limit usefulness
  0  = not useful to the stated audience

HARD FAILS (automatic: pass must be false regardless of score):
- broken_code       : code that will not execute (coding tasks only)
- dangerous_content : harmful, unethical, or dangerous material
- completely_offtopic: response does not address the goal at all
- fabricated_citations: invented sources, fake quotes, or made-up statistics

REQUIRED JSON SCHEMA:
{
    "scores": {
        "completeness": <integer 0–25>,
        "accuracy": <integer 0–25>,
        "clarity": <integer 0–25>,
        "usefulness": <integer 0–25>
    },
    "total_score": <integer — must equal exact sum of the four scores>,
    "pass": <boolean — true if total_score >= threshold AND no hard fails>,
    "hard_fails": [<string>, ...],
    "rationale": "<one paragraph, 2–4 sentences, explaining the key scores>"
}

CALIBRATION EXAMPLES:
- Score 85+: Thorough, accurate, well-written, immediately useful. Few or no issues.
- Score 70–84: Good. Meets the goal. Minor weaknesses that don't undermine value.
- Score 55–69: Adequate but needs improvement. One or two significant gaps.
- Score 40–54: Below average. Multiple gaps or a significant error.
- Score <40: Fundamentally flawed, very incomplete, or off-topic.

COMMON FAILURE MODES TO AVOID:
- Do not give every draft a score of 75 regardless of quality (score inflation).
- Do not add text outside the JSON object.
- Do not omit the rationale field.
- Ensure total_score exactly equals the sum of the four category scores.
```

---

## 17.7 Final Synthesizer — `prompts/synthesizer.txt`

```bash
code prompts/synthesizer.txt
```

```
You are the Final Synthesizer agent in a high-quality multi-agent AI pipeline.

YOUR ROLE:
You receive the best draft produced by the improvement loop. This draft has
already been critiqued and revised at least once and has been scored as
meeting the quality threshold. Your job is to polish it into a clean,
presentation-ready final deliverable.

WHAT YOU ARE POLISHING (not rewriting):
The substance, structure, and content have already been validated. You are
the final editor, not a new author. Your changes should be invisible to the
reader — the output should feel like one expert wrote it from scratch.

WHAT TO DO:
- Fix any remaining grammatical errors or typos.
- Smooth any awkward phrasing or abrupt transitions between sections.
- Ensure all headings use consistent formatting and capitalization.
- Ensure code blocks (if any) are properly fenced with ```python.
- Remove any artifacts from the revision process:
    Examples of artifacts to remove:
    - "In response to the feedback about..."
    - "As the critic correctly noted..."
    - "I have improved the section on..."
    - "Note: this has been revised from the previous version..."
- Tighten any verbose passages without removing content.
- Ensure the opening sentence is strong and sets up the content well.
- Ensure the closing is conclusive — not "I hope this helps" or trailing off.

WHAT NOT TO DO:
- Do not remove sections, shorten the content, or change the substance.
- Do not add new information or opinions that were not in the draft.
- Do not add meta-commentary ("Here is the final polished version:").
- Do not add a preamble or closing note from you. Output the deliverable directly.
- Do not change code logic — only fix formatting of code blocks.

OUTPUT:
The complete polished deliverable, ready for the user to read or use directly.
No labels. No preamble. Just the content.
```

---

## 17.8 Common prompt failure modes and fixes

| Symptom | Agent | Fix |
|---|---|---|
| Short, shallow drafts | Builder | Add: "Do not produce fewer than 400 words unless explicitly instructed." |
| Vague critique ("needs improvement") | Critic | Add: "Vague feedback is unacceptable. Every issue must name a location and a specific fix." |
| Fixer ignores most critique points | Fixer | Add: "Before outputting, mentally check each issue in the critique and confirm it has been addressed." |
| Judge returns prose instead of JSON | Judge | Add at the very top: "YOUR FIRST CHARACTER MUST BE { AND YOUR LAST CHARACTER MUST BE }." |
| Judge scores always 70–75 | Judge | Add: "Do not cluster scores around 70–75. Use the full 0–100 range. Reserve 70–75 for drafts that are genuinely average." |
| Synthesizer rewrites the whole draft | Synthesizer | Add: "Do not rewrite. Edit only. Every paragraph in your output must trace directly to a paragraph in the draft you received." |
| Supervisor picks wrong mode | Supervisor | Add explicit examples: "If the goal asks to 'write code', the mode is coding. If it asks to 'explain', the mode is study." |
| Planner creates only 2–3 steps | Planner | Add: "A plan with fewer than 4 steps is almost always incomplete. Err toward more steps, not fewer." |

---

## 17.9 How to improve prompts over time

Prompts decay in effectiveness as you work on new task types. The best improvement
process:

1. After a run where the output quality disappointed you, check which agent produced
   the weakest output. Read its saved file in `runs/<timestamp>/`.
2. Identify whether the problem was the prompt or the model. Test the same prompt
   with a stronger model before changing the prompt.
3. Add one specific rule to the prompt that addresses the failure mode. Do not
   rewrite the whole prompt.
4. Run the same goal again and compare outputs.
5. Commit prompt changes to Git with a message describing what behavior changed.

Keep prompt files under Git version control. A prompt change that breaks quality
can be rolled back with `git checkout prompts/critic.txt`.

---

*End of Sections 16 and 17.*

---

> **Next sections to write:** Section 18 (Configuration and API Scalability),
> Section 19 (Logging and Debugging), and Section 20 (Common Issues).

---

# SECTION 18 — Configuration Files and Future API Scalability

## 18.1 Design philosophy

The system is local-first by default. No API keys. No internet connection after models are downloaded. No cost. But the
architecture is designed so that swapping from Ollama to OpenAI, Anthropic, or any
other provider requires changing one config value — not rewriting Python code.

This is achieved through a **model adapter layer**: all agent code calls a single
`call_model()` function on `BaseAgent`. That function currently calls Ollama. To
add a new provider, you write a new adapter class that implements the same interface
and point the config at it. The agents never know or care which provider is running.

---

## 18.2 Finalize `config/models.yaml`

This is the full version of the config file. It supports all four model profiles
defined in Section 6. You switch profiles by changing one value: `active_profile`.
No Python code changes needed.

```bash
code config/models.yaml
```

```yaml
# config/models.yaml
#
# Model configuration for the Local AI Orchestrator.
# All agents read their model assignments from here.
# Change values here to swap models without editing Python code.
#
# PROVIDER OPTIONS (default: ollama):
#   ollama    — local models via Ollama (free, no API key needed)
#   openai    — OpenAI API (requires OPENAI_API_KEY in .env) [future]
#   anthropic — Anthropic API (requires ANTHROPIC_API_KEY in .env) [future]

provider: ollama

ollama:
  base_url: "http://localhost:11434"
  keep_alive: "5m"

# ── ACTIVE PROFILE ────────────────────────────────────────────────────────────
# Set this to switch the entire model stack without editing individual roles.
# Options: bootstrap | serious | coding | fast
#
# bootstrap : llama3.2:3b for everything — use to verify the pipeline works
# serious   : qwen2.5:14b builder, phi4:14b judge, gemma3:12b critic — real work
# coding    : qwen2.5-coder:14b builder/fixer — Python and debugging tasks
# fast      : llama3.1:8b builder, llama3.2:3b for routing — quick iteration
#
# Start with bootstrap. Switch to serious once the loop runs end-to-end.

active_profile: bootstrap

# ── MODEL PROFILES ────────────────────────────────────────────────────────────

profiles:

  bootstrap:
    # Purpose: verify pipeline code works, tune prompts, debug orchestration.
    # NOT the quality target for real work. Switch to 'serious' when loop works.
    supervisor:  "llama3.2:3b"
    planner:     "llama3.2:3b"
    builder:     "llama3.2:3b"
    critic:      "llama3.2:3b"
    fixer:       "llama3.2:3b"
    judge:       "llama3.2:3b"
    synthesizer: "llama3.2:3b"

  serious:
    # Purpose: recommended default for writing, planning, study, and general tasks.
    # Builder (Qwen) and Judge (Phi-4) are from different model families
    # so the Judge applies a genuinely independent evaluation.
    # Critic (Gemma) also from a different family for diverse perspective.
    supervisor:  "llama3.1:8b"
    planner:     "llama3.1:8b"
    builder:     "qwen2.5:14b"
    critic:      "gemma3:12b"
    fixer:       "qwen2.5:14b"
    judge:       "phi4:14b"
    synthesizer: "qwen2.5:14b"

  coding:
    # Purpose: coding and debugging tasks using a code-specialized builder/fixer.
    # Pull qwen2.5-coder:14b before activating this profile.
    supervisor:  "llama3.1:8b"
    planner:     "llama3.1:8b"
    builder:     "qwen2.5-coder:14b"
    critic:      "gemma3:12b"
    fixer:       "qwen2.5-coder:14b"
    judge:       "phi4:14b"
    synthesizer: "qwen2.5:14b"

  fast:
    # Purpose: quick testing, prompt iteration, or when RAM is constrained.
    # Lower quality than 'serious'. Do not use for final deliverables.
    supervisor:  "llama3.2:3b"
    planner:     "llama3.2:3b"
    builder:     "llama3.1:8b"
    critic:      "llama3.2:3b"
    fixer:       "llama3.1:8b"
    judge:       "llama3.1:8b"
    synthesizer: "llama3.1:8b"

# ── PER-MODE OVERRIDES ────────────────────────────────────────────────────────
# These override specific roles within the active profile.
# Leave commented out unless you need fine-grained control.

# mode_overrides:
#   coding:
#     builder: "qwen2.5-coder:14b"
#     fixer:   "qwen2.5-coder:14b"
#   debugging:
#     builder: "qwen2.5-coder:14b"
#     fixer:   "qwen2.5-coder:14b"

# ── INFERENCE DEFAULTS ────────────────────────────────────────────────────────
defaults:
  temperature: 0.7
  num_ctx: 4096

# ── MEMORY MANAGEMENT ────────────────────────────────────────────────────────
# keep_alive controls how long Ollama holds a model in RAM after a call.
# "5m"  = 5 minutes — recommended for sequential pipeline calls
# "0"   = unload immediately — use if you need to load a different large model next
# "-1"  = keep indefinitely — not recommended on 24 GB
memory:
  keep_alive: "5m"
```

Save the file.

**How to switch profiles:** Change `active_profile: bootstrap` to
`active_profile: serious` (or `coding` or `fast`). The config loader reads this
value and applies the matching profile's model assignments to every agent.

**Update `orchestrator/config_loader.py`** to read the active profile. Replace the
`get_model_for_role()` function with this version:

```python
def get_model_for_role(role: str, mode: str = "general") -> str:
    """
    Return the model name for a given agent role.
    Checks mode_overrides first, then the active profile, then a fallback.
    """
    cfg = load_models_config()

    # Check per-mode overrides first (most specific)
    mode_overrides = cfg.get("mode_overrides", {}).get(mode, {})
    if role in mode_overrides:
        return mode_overrides[role]

    # Use the active profile
    active = cfg.get("active_profile", "bootstrap")
    profiles = cfg.get("profiles", {})
    profile_models = profiles.get(active, profiles.get("bootstrap", {}))
    if role in profile_models:
        return profile_models[role]

    # Final fallback
    return cfg.get("models", {}).get(role, "llama3.2:3b")


def get_active_profile() -> str:
    """Return the name of the currently active model profile."""
    return load_models_config().get("active_profile", "bootstrap")
```

---

## 18.3 Write the config loader

**File path:** `orchestrator/config_loader.py`

```bash
code orchestrator/config_loader.py
```

```python
"""
orchestrator/config_loader.py

Loads and caches configuration from config/models.yaml and config/modes.yaml.
All pipeline code should use these functions instead of reading YAML directly.
"""

from pathlib import Path
import yaml

_CONFIG_DIR = Path("config")
_models_cache: dict | None = None
_modes_cache: dict | None = None


def load_models_config() -> dict:
    global _models_cache
    if _models_cache is None:
        path = _CONFIG_DIR / "models.yaml"
        with open(path, encoding="utf-8") as f:
            _models_cache = yaml.safe_load(f)
    return _models_cache


def get_provider() -> str:
    """Return the active provider name (e.g. 'ollama')."""
    return load_models_config().get("provider", "ollama")


def get_model_for_role(role: str, mode: str = "general") -> str:
    """
    Return the model name for a given agent role and optional mode.
    Checks mode_overrides first, falls back to models defaults.
    """
    cfg = load_models_config()
    mode_overrides = cfg.get("mode_overrides", {}).get(mode, {})
    if role in mode_overrides:
        return mode_overrides[role]
    return cfg.get("models", {}).get(role, "llama3.2:3b")


def get_ollama_base_url() -> str:
    cfg = load_models_config()
    return cfg.get("ollama", {}).get("base_url", "http://localhost:11434")


def get_inference_defaults() -> dict:
    cfg = load_models_config()
    return cfg.get("defaults", {"temperature": 0.7, "num_ctx": 4096})


def get_keep_alive() -> str:
    cfg = load_models_config()
    return cfg.get("memory", {}).get("keep_alive", "5m")


def reload_config():
    """Force reload of cached configs (useful after editing YAML files)."""
    global _models_cache, _modes_cache
    _models_cache = None
    _modes_cache = None
```

Save the file.

---

## 18.4 The model adapter interface

This is the layer that lets you swap providers without rewriting agents. Currently
only the Ollama adapter exists. Adding a new provider means writing a new class
that implements `ModelAdapter`.

**File path:** `orchestrator/adapters.py`

```bash
code orchestrator/adapters.py
```

```python
"""
orchestrator/adapters.py

Model adapter interface and implementations.

All agent calls go through a ModelAdapter subclass. The active adapter is
selected by the 'provider' field in config/models.yaml. Adding a new provider
(e.g. OpenAI) requires only:
  1. Writing a new subclass of ModelAdapter
  2. Registering it in get_adapter()
  3. Setting provider: openai in models.yaml
  4. Providing the API key in .env

No changes to agent code are needed.
"""

import os
import requests
from abc import ABC, abstractmethod

from orchestrator.config_loader import (
    get_ollama_base_url, get_inference_defaults, get_keep_alive
)


# ── Base interface ────────────────────────────────────────────────────────────

class ModelAdapter(ABC):
    """
    Abstract base class for all model provider adapters.
    Every adapter must implement call().
    """

    @abstractmethod
    def call(self, model: str, prompt: str,
             temperature: float = 0.7, num_ctx: int = 4096) -> str:
        """
        Send a prompt to the model and return the response text.

        Args:
            model:       Provider-specific model identifier.
            prompt:      The full prompt string (system + user content merged).
            temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative).
            num_ctx:     Context window size in tokens.

        Returns:
            The model's response as a plain string.

        Raises:
            RuntimeError if the call fails after all retries.
        """


# ── Ollama adapter (default) ──────────────────────────────────────────────────

class OllamaAdapter(ModelAdapter):
    """
    Calls the local Ollama server at http://localhost:11434.
    No API key required. All inference is local and free.
    """

    def __init__(self):
        self.base_url = get_ollama_base_url()
        self.keep_alive = get_keep_alive()

    def call(self, model: str, prompt: str,
             temperature: float = 0.7, num_ctx: int = 4096) -> str:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": temperature,
                "num_ctx": num_ctx,
            },
        }
        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=180,
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Is the Ollama app running? Run: open -a Ollama"
            )
        except requests.exceptions.Timeout:
            raise RuntimeError(
                f"Ollama timed out on model '{model}'. "
                "Try a smaller model or check memory pressure."
            )
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"Ollama HTTP error: {e} — {resp.text[:300]}")


# ── Future adapter stubs ──────────────────────────────────────────────────────
# These are NOT implemented and will raise NotImplementedError if called.
# They exist as stubs to show how to add providers later.

class OpenAIAdapter(ModelAdapter):
    """
    Future: OpenAI API adapter.
    Requires: pip install openai
    Requires: OPENAI_API_KEY in .env
    To activate: set provider: openai in config/models.yaml
    """

    def call(self, model: str, prompt: str,
             temperature: float = 0.7, num_ctx: int = 4096) -> str:
        raise NotImplementedError(
            "OpenAI adapter is not yet implemented. "
            "Set provider: ollama in config/models.yaml to use local models. "
            "To implement: pip install openai, add OPENAI_API_KEY to .env, "
            "then replace this raise with the openai.ChatCompletion.create() call."
        )


class AnthropicAdapter(ModelAdapter):
    """
    Future: Anthropic Claude API adapter.
    Requires: pip install anthropic
    Requires: ANTHROPIC_API_KEY in .env
    To activate: set provider: anthropic in config/models.yaml
    """

    def call(self, model: str, prompt: str,
             temperature: float = 0.7, num_ctx: int = 4096) -> str:
        raise NotImplementedError(
            "Anthropic adapter is not yet implemented. "
            "Set provider: ollama in config/models.yaml to use local models."
        )


# ── Adapter factory ───────────────────────────────────────────────────────────

_adapter_cache: ModelAdapter | None = None


def get_adapter() -> ModelAdapter:
    """
    Return the active ModelAdapter based on config/models.yaml provider setting.
    Cached after first call — call reload_config() to reset.
    """
    global _adapter_cache
    if _adapter_cache is not None:
        return _adapter_cache

    from orchestrator.config_loader import get_provider
    provider = get_provider()

    if provider == "ollama":
        _adapter_cache = OllamaAdapter()
    elif provider == "openai":
        _adapter_cache = OpenAIAdapter()
    elif provider == "anthropic":
        _adapter_cache = AnthropicAdapter()
    else:
        raise ValueError(
            f"Unknown provider '{provider}' in config/models.yaml. "
            "Valid options: ollama, openai, anthropic"
        )

    return _adapter_cache
```

Save the file.

---

## 18.5 Update `BaseAgent` to use the adapter

Open `agents/base_agent.py`. Replace the `call_model()` method body with:

```python
    def call_model(self, prompt: str) -> str:
        """Send prompt through the configured model adapter with retry."""
        from orchestrator.adapters import get_adapter
        from orchestrator.config_loader import get_inference_defaults

        adapter = get_adapter()
        defaults = get_inference_defaults()
        temperature = getattr(self, "temperature", defaults.get("temperature", 0.7))
        num_ctx = getattr(self, "num_ctx", defaults.get("num_ctx", 4096))

        for attempt in range(1, self.max_retries + 2):
            try:
                text = adapter.call(
                    model=self.model,
                    prompt=prompt,
                    temperature=temperature,
                    num_ctx=num_ctx,
                )
                if not text:
                    raise ValueError("Adapter returned empty response.")
                return text
            except RuntimeError as e:
                if attempt <= self.max_retries:
                    print(f"  [WARN] {self.role} attempt {attempt} failed: {e}. Retrying...")
                    time.sleep(3)
                    continue
                self._fatal(str(e))
            except ValueError as e:
                if attempt <= self.max_retries:
                    print(f"  [WARN] {self.role} empty response, retrying...")
                    time.sleep(2)
                    continue
                self._fatal(str(e))

        self._fatal("All retry attempts exhausted.")
```

Now `BaseAgent` never imports `requests` directly — all HTTP logic lives in the
adapter. Adding a new provider in the future does not touch `base_agent.py` at all.

---

## 18.6 Create the `.env` file (for future API keys)

Even though no API keys are used in the default build, create the `.env` file now
as an empty placeholder so the structure is ready:

```bash
touch .env
code .env
```

```bash
# .env — environment variables for the Local AI Orchestrator
# This file is excluded from Git (.gitignore). Never commit it.

# Ollama server URL (change if you moved Ollama to a different port)
OLLAMA_HOST=http://localhost:11434

# Future: add API keys here when upgrading to paid providers
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
```

Save the file. Verify it is already in `.gitignore`:
```bash
grep ".env" .gitignore
```
Expected output: `.env` or `.env.*` should appear. If not, add it:
```bash
echo ".env" >> .gitignore
```

To load `.env` values into the shell environment when using `activate.sh`, add
this to `activate.sh` (open it and add after the `source .venv/bin/activate` line):
```bash
# Load .env if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi
```

---

## 18.7 How to lower memory usage via config

Switch to the `fast` profile in `config/models.yaml`:

```yaml
active_profile: fast
```

This keeps peak RAM under 5 GB and is useful when other applications are
consuming memory. If you need to go even lower:

```yaml
active_profile: bootstrap
```

And add to the `memory` block:
```yaml
memory:
  keep_alive: "0"    # unload model immediately after each call
```

The `keep_alive: "0"` setting means each model call pays a reload cost from disk
(2–5 seconds for 3B–8B models on your NVMe SSD) but uses no RAM between calls.
For sequential pipeline runs this is a small overhead; for real-time testing it
can feel noticeably slower.

**RAM usage by profile (peak, one model loaded at a time):**

| Profile | Peak RAM | Notes |
|---------|----------|-------|
| bootstrap | ~2.5 GB | All calls use llama3.2:3b |
| fast | ~4.9 GB | Builder/Fixer use llama3.1:8b |
| serious | ~9.0 GB | Builder/Judge use 14B models |
| coding | ~9.0 GB | Builder/Fixer use qwen2.5-coder:14b |

All four profiles fit comfortably within your 24 GB with 15+ GB headroom even
at peak, so memory pressure should not be an issue unless you run very many
other large applications simultaneously.

---

## 18.8 How to add an OpenAI provider later (no code changes needed)

When you are ready to optionally use OpenAI for higher-quality output:

1. Install the SDK:
   ```bash
   $ pip install openai
   ```

2. Add your API key to `.env`:
   ```bash
   OPENAI_API_KEY=sk-your-key-here
   ```

3. Implement `OpenAIAdapter.call()` in `orchestrator/adapters.py`:
   ```python
   def call(self, model: str, prompt: str,
            temperature: float = 0.7, num_ctx: int = 4096) -> str:
       from openai import OpenAI
       client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
       response = client.chat.completions.create(
           model=model,
           messages=[{"role": "user", "content": prompt}],
           temperature=temperature,
           max_tokens=num_ctx,
       )
       return response.choices[0].message.content.strip()
   ```

4. Switch the provider in `config/models.yaml`:
   ```yaml
   provider: openai
   models:
     builder: "gpt-4o"
     judge:   "gpt-4o-mini"
   ```

5. No other files need to change. The agents, prompts, and pipeline logic are
   all provider-agnostic.

To switch back to local Ollama: change `provider: openai` back to `provider: ollama`.

---

# SECTION 19 — Logging, Debugging, and Error Handling

## 19.1 Set up structured logging

**File path:** `orchestrator/logger.py`

```bash
code orchestrator/logger.py
```

```python
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
```

Save the file.

---

## 19.2 Wire logging into `run.py`

At the top of `run.py`, add:
```python
from orchestrator.logger import get_logger
```

At the start of `run_pipeline()`, create the logger using the run directory name
as the run ID:
```python
    log = get_logger(run_dir.name)
    log.run_start(goal=goal, model_main=model_main, model_fast=model_fast,
                  max_loops=max_loops, threshold=threshold)
```

Wrap each agent call with timing and logging:
```python
    import time

    # Example: wrapping the Builder call
    t0 = time.time()
    log.agent_start("builder", model_main)
    draft = builder.run(goal=refined_goal, plan=plan)
    log.agent_end("builder", chars=len(draft),
                  elapsed_ms=int((time.time() - t0) * 1000))
```

After each Judge verdict:
```python
    log.score(
        iteration=iteration,
        score=score,
        passed=verdict["pass"],
        category_scores=verdict.get("scores", {}),
        hard_fails=verdict.get("hard_fails", []),
    )
```

At the end of the pipeline:
```python
    log.stop(reason=stop_reason, final_score=best_score,
             iterations=summary["iterations_run"])
```

---

## 19.3 How to inspect saved log entries

The log file at `logs/pipeline.log` contains one JSON object per line (JSONL format).
Each line is independently parseable.

**View the last 20 log entries:**
```bash
tail -20 logs/pipeline.log
```

**Pretty-print the last entry:**
```bash
tail -1 logs/pipeline.log | python3 -m json.tool
```

**Show only score events:**
```bash
grep '"event": "score"' logs/pipeline.log | python3 -m json.tool
```

**Show only errors:**
```bash
grep '"event": "agent_error"' logs/pipeline.log
```

**Show the full trace for one run (replace RUN_ID with your run folder name):**
```bash
grep '"run_id": "20240115_153042"' logs/pipeline.log | python3 -c "
import sys, json
for line in sys.stdin:
    e = json.loads(line)
    print(f\"{e['ts']} | {e['event']:<20} | {json.dumps({k:v for k,v in e.items() if k not in ('ts','run_id','event')})}\")"
```

---

## 19.4 What to log — quick reference

| What | Log event | Why |
|---|---|---|
| Run start | `run_start` | Anchors all subsequent entries for this run |
| Each agent start | `agent_start` | Lets you see which agent was running when a crash occurred |
| Each agent end | `agent_end` | Tracks output size and time per agent |
| Every Judge score | `score` | Score history, category breakdown, hard fails |
| Code verification | `code_verification` | Confirms whether generated code actually ran |
| Loop stop reason | `run_stop` | Audits whether the loop ended for the right reason |
| Any error | `agent_error` | Full error message and which attempt it was |
| JSON parse failures | `json_parse_failure` | Diagnoses Judge prompt issues |
| Slow responses | `warning` | Flags model calls >60s for performance review |

---

## 19.5 How to handle malformed model outputs

The pipeline encounters three types of malformed output:

**Type 1: Empty response**
Handled in `BaseAgent.call_model()` — retries up to `max_retries` times. After
all retries, calls `self._fatal()` which prints the error and exits with code 1.
Never silently returns an empty string.

**Type 2: JSON expected but prose returned (Judge)**
Handled in `JudgeAgent._parse_json()` — three levels of extraction (direct parse,
strip fences, find first `{...}` block). After three model call attempts, falls
back to `_fallback_verdict()` which returns score 40, `hard_fail: ["judge_parse_error"]`.
Logs the raw output via `log.json_parse_failure()`.

**Type 3: Truncated output (model hit context limit)**
Symptom: Agent output ends mid-sentence or mid-code-block. The model ran out of
output tokens. Fix: Reduce `num_ctx` to allow more output room, or shorten the
input prompt. Add this check to `BaseAgent.call_model()` if needed:
```python
if text.endswith(("...", "…")) or len(text) > 3000 and not text[-1] in ".!?\n}":
    log.warning("Possible truncated output", context=f"{self.role} response")
```

---

## 19.6 How to retry safely

The retry pattern in `BaseAgent.call_model()` follows these rules:

1. **Retry on transient errors** (timeout, empty response) — these can succeed
   on the next attempt.
2. **Do not retry on connection refused** — if Ollama is not running, retrying
   will not help. Fail fast with a clear message.
3. **Wait between retries** — `time.sleep(3)` prevents hammering a temporarily
   overloaded server.
4. **Limit retries** — default `max_retries=2` means 3 total attempts. More than
   3 attempts on a bad model call wastes time.
5. **Log every retry** — so you can see in the log that a retry occurred.

---

## 19.7 How to recover if the app crashes mid-run

If `run.py` crashes (KeyboardInterrupt, unhandled exception, Ollama crash):

**Step 1:** Check what was saved:
```bash
ls -la runs/$(ls -t runs/ | head -1)/
```

All files saved before the crash are intact. The crash only loses the current
agent's in-progress output (which was never saved).

**Step 2:** Read the log to find where it crashed:
```bash
tail -30 logs/pipeline.log
```
The last `agent_start` entry tells you which agent was running. The absence of
a corresponding `agent_end` confirms that agent did not finish.

**Step 3:** You can resume manually from the last saved file. For example, if
the crash happened during the Fixer in loop 2, you have:
- `loop01_critic.txt` — saved
- `loop01_fixer.txt` — saved
- `loop01_judge.json` — saved
- `loop02_critic.txt` — saved
- `loop02_fixer.txt` — **missing (crash happened here)**

You can resume from `loop02_critic.txt` by manually running the Fixer and Judge
with a small script, or simply re-run the full pipeline — the added cost is one
Builder call and repeating the completed loops.

**Step 4:** If Ollama crashed (not just the Python script):
```bash
curl http://localhost:11434
```
If this fails, restart Ollama:
```bash
pkill -f "ollama" && sleep 2 && open -a Ollama
```
Wait 5 seconds, then re-run the pipeline.

---

# SECTION 20 — Common Issues and Remedies

---

## Issue 1: Ollama CLI installed but server not running

**Symptom:** `ollama --version` works but returns "could not connect" warning.
`curl http://localhost:11434` returns "Connection refused".

**Cause:** The Ollama server process is not running. The CLI binary exists but
the background server daemon is stopped or was never started.

**Fix:**
```bash
open -a Ollama
# Wait 5 seconds
curl http://localhost:11434
```
Expected: `Ollama is running`

**Verify:** `ollama list` returns without an error.

---

## Issue 2: Ollama app not open / menu bar icon missing

**Symptom:** You cannot find the Ollama icon in the macOS menu bar.

**Fix:**
```bash
ls /Applications/Ollama.app
```
If it exists: `open -a Ollama`
If it does not exist: download and reinstall from https://ollama.com/download

**Verify:** A small llama icon appears in the top-right menu bar.

---

## Issue 3: `ollama: command not found`

**Symptom:** Running `ollama` in Terminal gives "command not found".

**Cause:** The Ollama CLI binary is not on your PATH.

**Fix:**
```bash
ls /usr/local/bin/ollama
```
If the file exists:
```bash
echo 'export PATH="/usr/local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```
If the file does not exist, reinstall Ollama from https://ollama.com/download.

**Verify:** `ollama --version` returns a version number.

---

## Issue 4: Model not found (`model 'X' not found`)

**Symptom:** Pipeline errors with "model not found" or Ollama logs show the
model name is unrecognized.

**Cause:** The model was not pulled, the name is misspelled, or a tag is wrong.

**Fix:**
```bash
# See what you have
ollama list

# Pull the missing model (use whatever model name config/models.yaml expects)
ollama pull llama3.2:3b         # Bootstrap profile
# or
ollama pull qwen2.5:14b         # Serious Work profile — Builder/Fixer/Synthesizer

# Check the exact name after pulling
ollama list
```
Update `config/models.yaml` with the exact tag shown in `ollama list`, or switch
`active_profile` to a profile whose models you have already pulled.

**Verify:** `ollama run llama3.2:3b "hello"` (or whichever model was missing) returns a response.

---

## Issue 5: Model responses are very slow (>2 minutes per call)

**Symptom:** Each agent call takes 2+ minutes. The terminal appears frozen.

**Cause:** Memory pressure — the Mac is swapping the model to disk — or the
model simply needs more time on longer prompts (14B models take 20–50 seconds
on typical prompts, which is normal and not a problem).

**Fix — Step 1:** Distinguish slow vs. broken.
A 14B model responding in 30–60 seconds is normal on M3. Only investigate if
a response takes 2+ minutes on a short prompt.

**Fix — Step 2:** Check memory pressure:
Open Activity Monitor → Memory tab. If pressure is yellow or red, close other
large apps (browsers with many tabs, Slack, Spotify, Xcode).

**Fix — Step 3:** Drop to the Fast profile temporarily:
```yaml
# config/models.yaml
active_profile: fast
```
```bash
python run.py --goal "..." --model-main llama3.1:8b --model-fast llama3.2:3b
```

**Fix — Step 4:** Unload models between calls if RAM is tight:
```bash
export OLLAMA_KEEP_ALIVE=0
```

**Verify:** `ollama run llama3.2:3b "one word answer: color of sky"` responds
in under 15 seconds. If the serious-profile model (e.g. `qwen2.5:14b`) takes
30–60 seconds, that is expected — do not treat it as a problem.

---

## Issue 5a: 14B model is noticeably slower than expected

**Symptom:** `qwen2.5:14b` or `phi4:14b` takes 90+ seconds on short prompts.
The Bootstrap profile (`llama3.2:3b`) is fast, but Serious Work profile is painfully slow.

**Cause:** The model is being loaded from disk on every call (model unloading
between calls), or another app is competing for GPU/RAM bandwidth.

**Fix — Step 1:** Ensure `keep_alive` is not set to `"0"`:
```yaml
# config/models.yaml
memory:
  keep_alive: "5m"
```
With `keep_alive: "5m"`, a 14B model loaded for the Builder call stays warm
for the Fixer and Synthesizer calls in the same pipeline run, avoiding repeated
disk loads.

**Fix — Step 2:** Check if another Ollama model is still loaded from a previous
session, consuming RAM:
```bash
curl http://localhost:11434/api/ps
```
**What this does:** Lists which models Ollama currently has loaded in memory.
If a different model is loaded, it may be occupying RAM. Unload it:
```bash
curl -X POST http://localhost:11434/api/generate \
  -d '{"model":"<other-model-name>","keep_alive":0}' 2>/dev/null
```

**Verify:** Second and third calls to the same 14B model in a pipeline run
should be noticeably faster than the first (model is warm in RAM).

---

## Issue 6: Mac memory pressure (red in Activity Monitor)

**Symptom:** Mac fans spin loudly. Activity Monitor Memory Pressure is red.
Swap Used is above 2GB. Everything is slow.

**Cause:** Too many applications in memory. Note: even with the Serious Work
profile (14B models at ~9 GB peak), your 24 GB M3 has plenty of headroom.
Memory pressure with this system usually means browser tabs or other large
apps, not the models themselves.

**Fix:**
1. Close Chrome (especially with many tabs), Slack, Spotify, Xcode, or
   other large apps. Each Chrome tab can use 200MB–1GB.
2. Unload the current Ollama model to recover RAM immediately:
   ```bash
   $ curl -X POST http://localhost:11434/api/generate \
     -d '{"model":"qwen2.5:14b","keep_alive":0}' 2>/dev/null
   ```
   **What this does:** Forces Ollama to unload the named model from RAM.
   Replace `qwen2.5:14b` with whichever model was last used.
3. Wait 30 seconds for memory pressure to drop to green.
4. If pressure stays red: switch to the `fast` profile for this session.

**Verify:** Activity Monitor Memory Pressure returns to green.

---

## Issue 7: `python3: command not found` or `python: command not found`

**Symptom:** Terminal says the command is not found even though Python is installed.

**Fix:**
```bash
# Find where Python 3.14 was installed
find /Library/Frameworks /usr/local /opt/homebrew -name "python3.14" 2>/dev/null

# Add the correct path to ~/.zshrc
echo 'export PATH="/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
python3 --version
```

**Verify:** `python3 --version` returns `Python 3.14.0`.

---

## Issue 8: `pip install` fails with a build error

**Symptom:** `pip install -r requirements.txt` exits with:
```
error: legacy-install-failure
note: This error originates from a subprocess
```

**Cause:** A package does not have a pre-built wheel for Python 3.14 and cannot
compile from source.

**Fix:** Switch to Python 3.12 (see Section 5.9 for full steps):
```bash
brew install python@3.12
deactivate
rm -rf .venv
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Verify:** `pip install -r requirements.txt` completes without errors.

---

## Issue 9: Python 3.14 package compatibility issues with LangGraph

**Symptom:** `import langgraph` fails with an ImportError or AttributeError
on Python 3.14.

**Cause:** LangGraph or one of its dependencies uses an API that changed in
Python 3.14.

**Fix:** Check if a newer version of LangGraph fixes it:
```bash
pip install --upgrade langgraph langchain-core langchain-ollama
```
If still broken, switch to Python 3.12 as described in Section 5.9.

**Verify:** `python -c "import langgraph; print(langgraph.__version__)"` prints
a version without errors.

---

## Issue 10: VS Code does not detect the virtual environment

**Symptom:** VS Code shows import errors for `requests`, `yaml`, or `langgraph`
even though `pip install` succeeded.

**Cause:** VS Code is using a different Python interpreter (system Python, not `.venv`).

**Fix:**
1. Press `Command + Shift + P` in VS Code.
2. Type `Python: Select Interpreter`.
3. Choose the entry showing `.venv` in the path.
4. If it does not appear, click `Enter interpreter path` and type:
   `/Users/andyyaro/Downloads/multi-modal-workflow/.venv/bin/python`
5. Open a new terminal in VS Code. The prompt should show `(.venv)`.

**Verify:** In the VS Code terminal: `python -c "import requests; print('OK')`

---

## Issue 11: LangGraph import errors (`cannot import name 'StateGraph'`)

**Symptom:** `from langgraph.graph import StateGraph` raises ImportError.

**Cause:** LangGraph version is too old, or the package is not installed in the
active environment.

**Fix:**
```bash
pip install --upgrade langgraph
python -c "from langgraph.graph import StateGraph; print('OK')"
```

If the error persists, check which Python is active:
```bash
which python
```
It must show the `.venv` path. If not, activate the environment:
```bash
source .venv/bin/activate
```

**Verify:** `python -c "from langgraph.graph import StateGraph; print('OK')"` prints OK.

---

## Issue 12: Streamlit does not launch

**Symptom:** `streamlit run app/streamlit_app.py` errors immediately.

**Cause A:** Streamlit not installed in the active environment.
**Fix:** `pip install streamlit` with the venv active.

**Cause B:** Import error in `streamlit_app.py` (e.g., agents module not found).
**Fix:** Run from the project root:
```bash
cd ~/Downloads/multi-modal-workflow
streamlit run app/streamlit_app.py
```

**Cause C:** A syntax error in the Streamlit file.
**Fix:** Check the Terminal output for a Python traceback and fix the line shown.

**Verify:** Browser opens at `http://localhost:8501` with the UI visible.

---

## Issue 13: Port 8501 or 11434 already in use

**Symptom:**
- Streamlit: `OSError: [Errno 48] Address already in use`
- Ollama: `Error: listen tcp: bind: address already in use`

**Fix — Streamlit (port 8501):**
```bash
lsof -ti :8501 | xargs kill -9
streamlit run app/streamlit_app.py
```

**Fix — Ollama (port 11434):**
```bash
lsof -i :11434
```
If it shows `ollama`, a server is already running — do not start another.
If it shows something else, change Ollama's port:
```bash
OLLAMA_HOST=127.0.0.1:11435 ollama serve
```
Then update `config/models.yaml`:
```yaml
ollama:
  base_url: "http://localhost:11435"
```

**Verify:** `curl http://localhost:11434` (or new port) returns `Ollama is running`.

---

## Issue 14: JSON parsing fails in Judge

**Symptom:** Judge always returns the fallback verdict. Log shows
`json_parse_failure` events. `raw_judge_output` appears in the saved JSON.

**Cause:** The Judge model is returning prose or markdown around the JSON instead
of a bare JSON object.

**Fix — Step 1:** Open `prompts/judge.txt` and add as the very first line:
```
CRITICAL: Your response must begin with { and end with }. Nothing else.
```

**Fix — Step 2:** If still failing, try a different model for the Judge role
that is better at instruction-following:
Switch to the Serious Work profile Judge, which is trained for structured output:
```yaml
# config/models.yaml
active_profile: serious   # phi4:14b as Judge — best JSON compliance of the four profiles
```
Or if staying on Bootstrap, explicitly override just the judge role via the
`mode_overrides` block (Section 18.2).

**Fix — Step 3:** Lower `num_ctx` in the Judge call. Long contexts increase the
chance of output format drift.

**Verify:** After a pipeline run, check `loop01_judge.json` — it should contain
a real JSON object, not a `raw_judge_output` key.

---

## Issue 15: Critic gives vague feedback

**Symptom:** Critique contains only "The draft is good but could be improved."
No specific issues listed. No locations. No fixes.

**Cause:** The Critic model is being sycophantic or the prompt is not firm enough.

**Fix:** Open `prompts/critic.txt` and add near the top:
```
MANDATORY: You must list a minimum of 3 numbered issues. Each issue MUST include
a specific location in the draft and a specific fix. "Make it clearer" is not a
valid fix. Vague feedback will be treated as a pipeline failure.
```
Also consider using a stronger model for the Critic by switching profiles:
```yaml
active_profile: serious   # gemma3:12b as Critic — trained for structured critique
```

**Verify:** Next critique contains at least 3 numbered, specific issues.

---

## Issue 16: Judge always fails everything (scores cluster 20–45)

**Symptom:** Nothing ever passes even after 5 loops. Scores never exceed 50.

**Cause:** The Judge model is applying an overly harsh interpretation of the
rubric, possibly because it misunderstands the scoring scale.

**Fix — Option A:** Lower the threshold for testing:
```bash
python run.py --goal "..." --threshold 45
```
If it now passes, the rubric is calibrated correctly — your real threshold was
just too high for the current model quality.

**Fix — Option B:** Recalibrate the rubric in `prompts/judge.txt`. Change the
score descriptions to be more generous:
```
20 = most key points addressed, minor gaps
```
instead of:
```
20 = significant sections missing
```

**Fix — Option C:** Use a different model for the Judge. Some smaller models
score more fairly than others on structured rubrics.

**Verify:** A clearly good draft (try pasting strong human-written text as the
goal output) scores above 70.

---

## Issue 17: Judge passes weak output on first try (scores always 80+)

**Symptom:** The loop never repeats because the Judge always gives high scores.
Final output quality is low despite high scores.

**Cause:** The Judge model is being too generous (score inflation).

**Fix:** Open `prompts/judge.txt` and add:
```
CALIBRATION REMINDER: Most first-draft responses score between 45–65.
A score above 80 should be rare and reserved for genuinely excellent output.
If you are giving scores above 75 on a first or second draft, reconsider.
```
Also raise the threshold:
```bash
python run.py --goal "..." --threshold 80
```

**Verify:** Run the pipeline on a deliberately weak goal ("write one word about
cats") — the Judge should score it below 40.

---

## Issue 18: Loop repeats too long / never stops

**Symptom:** Pipeline runs 5+ loops and does not converge. Score oscillates
between 55 and 65 without improving.

**Cause:** The Fixer is not substantially improving the output, the Judge
threshold is too high for the model, or `min_improvement` is too low.

**Fix — Option A:** Raise `min_improvement` to stop sooner when stalled:
```bash
python run.py --goal "..." --min-improvement 8
```

**Fix — Option B:** Lower the threshold so achievable quality can pass:
```bash
python run.py --goal "..." --threshold 60
```

**Fix — Option C:** Use a stronger model for Builder/Fixer:
```yaml
models:
  builder: "llama3.1:8b"
  fixer:   "llama3.1:8b"
```

**Verify:** Next run stops within `max_loops` iterations.

---

## Issue 19: Final output gets worse after revision

**Symptom:** `final_output.txt` is lower quality than `02_builder_draft_v0.txt`.
The Fixer or Synthesizer degraded the content.

**Cause:** The Fixer made unnecessary changes to sections that were already good,
or the Synthesizer removed content while "polishing."

**Fix — For Fixer:** Add to `prompts/fixer.txt`:
```
Do not change any section that the Critic did not explicitly criticize.
If a section was not mentioned in the critique, leave it exactly as it was.
```

**Fix — For Synthesizer:** Add to `prompts/synthesizer.txt`:
```
IMPORTANT: Do not remove any content. Do not shorten paragraphs. Do not
simplify explanations. Your only task is surface-level polish (grammar,
transitions, formatting). The content has already been validated.
```

**Fix — For tracking:** Remember that `best_draft.txt` always holds the
highest-scored version. If the Synthesizer degrades quality, compare
`final_output.txt` with `best_draft.txt` and use the latter.

**Verify:** After the fix, `final_output.txt` is at least as long and detailed
as `best_draft.txt`.

---

## Issue 20: App crashes mid-run

**Symptom:** `run.py` exits with an unhandled exception during a pipeline run.

**Fix — Step 1:** Read the full traceback in the terminal output.

**Fix — Step 2:** Check the log:
```bash
tail -20 logs/pipeline.log
```
The last `agent_start` event tells you where it crashed.

**Fix — Step 3:** Check if Ollama is still running:
```bash
curl http://localhost:11434
```
If not: `open -a Ollama`

**Fix — Step 4:** Common crash causes and fixes:
- `FileNotFoundError: prompts/builder.txt` → create the missing prompt file
- `KeyError: 'refined_goal'` in graph node → Supervisor node failed silently;
  check `logs/pipeline.log` for the error before this crash
- `JSONDecodeError` outside the Judge → the database save code received malformed
  data; check `run_summary.json` in the run folder

**Verify:** Re-run the pipeline with a simple goal to confirm it completes fully.

---

## Issue 21: Saved files are missing from `runs/`

**Symptom:** After a run, the `runs/` directory is empty or missing the run folder.

**Cause A:** `runs/` directory does not exist.
**Fix:** `mkdir -p runs`

**Cause B:** The pipeline crashed before saving any files (early exception).
**Fix:** Check terminal output for the error. The most common cause is an Ollama
connection error before the first agent call.

**Cause C:** You are running the script from a different directory, so `runs/`
is being created in the wrong place.
**Fix:**
```bash
cd ~/Downloads/multi-modal-workflow
python run.py --goal "test"
ls runs/
```

**Verify:** After a successful run, `ls runs/` shows a timestamped folder with
at least `00_supervisor.json` and `final_output.txt`.

---

## Issue 22: Permission errors on macOS

**Symptom:** `PermissionError: [Errno 13] Permission denied` when writing files.

**Cause A:** Trying to write outside the project directory (e.g., to `/tmp` or
`~/Documents`) without permission.
**Fix:** All pipeline output should go to `runs/` and `logs/` inside the project
directory. Do not change `RUNS_DIR` or `LOGS_DIR` to paths outside the project.

**Cause B:** macOS Full Disk Access is blocking writes to certain locations.
**Fix:** This should not happen for files inside `~/Downloads/`. If you moved the
project to a different location, check System Settings → Privacy & Security →
Full Disk Access and add Terminal.

**Cause C:** The `.venv` folder has wrong permissions (rare, happens if created
with `sudo`).
**Fix:**
```bash
ls -la .venv/bin/python
chmod +x .venv/bin/python
```

**Verify:** `python run.py --goal "test" --max-loops 1 --threshold 1` completes
and `ls runs/` shows new files.

---

## Issue 23: GitHub push errors

**Symptom:** `git push` fails with authentication errors or "remote rejected".

**Cause A:** Not authenticated with GitHub.
**Fix:** Use a Personal Access Token (PAT):
```bash
# When prompted for password, use your PAT, not your GitHub password
git push origin main
```
Or set up SSH keys (recommended for regular use):
```bash
ssh-keygen -t ed25519 -C "your@email.com"
cat ~/.ssh/id_ed25519.pub
# Copy the output and add it to GitHub → Settings → SSH and GPG keys
git remote set-url origin git@github.com:yourusername/multi-modal-workflow.git
git push origin main
```

**Cause B:** Accidentally trying to push to `main` with force-push protection.
**Fix:** Never use `git push --force` on main. Create a branch instead:
```bash
git checkout -b feature/my-changes
git push origin feature/my-changes
```

**Verify:** `git push` completes without errors and the commit appears on GitHub.

---

*End of Sections 18, 19, and 20.*

---

> **Next sections to write:** Section 21 (Testing the Whole System),
> Section 22 (Git and GitHub Setup), Section 23 (README Outline),
> Section 24 (Build Timeline), and Section 25 (Final Checklist).

---

# SECTION 21 — Testing the Whole System

Run these tests in order. Each one exercises a different part of the pipeline.
Do not skip a test because you "think it probably works." Verification is the
difference between a portfolio project and a working portfolio project.

---

## Test 1: Simple Writing Test

**Purpose:** Confirm the full pipeline produces coherent prose and saves all files.

**Command:**
```bash
python run.py \
    --goal "Write a 300-word explanation of why sleep deprivation hurts productivity, with two concrete examples." \
    --max-loops 2 \
    --threshold 65
```

**Expected behavior:**
- Supervisor identifies mode as `writing` or `general`.
- Planner produces a 4–6 step outline (intro, examples, conclusion).
- Builder produces 250–400 words of prose.
- Critic lists 2–5 specific issues.
- Fixer improves the draft.
- Judge scores between 60–85 on a writing task of this length.
- Synthesizer polishes without removing content.

**Expected saved files:**
```
runs/<timestamp>/
├── 00_supervisor.json
├── 01_planner_plan.txt
├── 02_builder_draft_v0.txt
├── loop01_critic.txt
├── loop01_fixer.txt
├── loop01_judge.json
├── best_draft.txt
├── final_output.txt
└── run_summary.json
```

**Expected score range:** 55–75 after one loop on Bootstrap (3B); 70–88 on Serious Work (14B).

**Pass criteria:**
- [ ] All 9 files exist in the run folder.
- [ ] `final_output.txt` contains at least 200 words.
- [ ] `loop01_judge.json` is valid JSON with all required keys.
- [ ] `run_summary.json` shows the correct `stop_reason`.

---

## Test 2: Planning Test

**Purpose:** Confirm planning mode produces structured, numbered output.

**Command:**
```bash
python run.py \
    --goal "Create a 3-week study plan for learning SQL from scratch, assuming 1 hour per day. Include topics, resources, and weekly milestones." \
    --max-loops 2 \
    --threshold 65
```

**Expected behavior:**
- Supervisor identifies mode as `planning`.
- Builder produces a structured plan with weekly phases and specific topics.
- Output should NOT be a wall of prose — it should use numbered steps, tables,
  or a clear week-by-week structure.
- Critic flags any weeks that are too vague or missing resources.

**Expected score range:** 62–80.

**Pass criteria:**
- [ ] `final_output.txt` contains explicit "Week 1", "Week 2", "Week 3" sections.
- [ ] Each week contains specific topics (not just "learn SQL basics").
- [ ] The Judge `mode` field in `run_summary.json` shows `planning`.

---

## Test 3: Coding Test

**Purpose:** Confirm coding mode produces runnable Python and that verification works.

**Command:**
```bash
python run.py \
    --goal "Write a Python function called fibonacci(n: int) -> list[int] that returns the first n Fibonacci numbers. Include 3 pytest test functions covering: n=0, n=1, and n=10." \
    --max-loops 3 \
    --threshold 70
```

**Expected behavior:**
- Supervisor identifies mode as `coding`.
- Builder produces a fenced ```python block with the function and test functions.
- Code verifier runs the file and pytest.
- If pytest passes all 3 tests: `loop01_code_run.txt` shows `PYTEST PASSED`.
- If the code has a bug: error is injected into the critique and the Fixer corrects it.
- Judge never passes a draft with `broken_code` in `hard_fails`.

**Expected saved files:** All standard files plus `loop01_code_run.txt`.

**Expected score range:** 65–88 after the code runs successfully.

**Pass criteria:**
- [ ] `loop01_code_run.txt` (or `loop02_code_run.txt`) shows `PYTEST PASSED`.
- [ ] `final_output.txt` contains a valid Python code block.
- [ ] No `broken_code` hard fail in the final passing verdict.
- [ ] You can copy the code from `final_output.txt` and run it yourself:
  ```bash
  $ python -c "
  def fibonacci(n):
      # paste code here
      pass
  print(fibonacci(10))
  "
  ```

---

## Test 4: Debugging Test

**Purpose:** Confirm debugging mode produces actionable root-cause analysis.

**Command:**
```bash
python run.py \
    --goal "My Python script crashes with: TypeError: unsupported operand type(s) for +: 'int' and 'str' on line 12. The line is: total = count + user_input. Diagnose the root cause and provide the exact fix." \
    --max-loops 2 \
    --threshold 65
```

**Expected behavior:**
- Supervisor identifies mode as `debugging`.
- Builder produces: problem restatement → root cause (type mismatch) → exact fix
  (`total = count + int(user_input)`) → verification steps.
- Output should NOT be generic ("check your types"). It should name the exact cause.

**Expected score range:** 60–82.

**Pass criteria:**
- [ ] `final_output.txt` correctly identifies the root cause as implicit string input.
- [ ] The fix shows the exact corrected line (`int(user_input)` or equivalent).
- [ ] Output includes a verification step.

---

## Test 5: Study/Explanation Test

**Purpose:** Confirm study mode builds understanding progressively.

**Command:**
```bash
python run.py \
    --goal "Explain what a Python context manager is, why you would use one, and show how to write a custom context manager using __enter__ and __exit__." \
    --max-loops 2 \
    --threshold 65
```

**Expected behavior:**
- Supervisor identifies mode as `study`.
- Output builds from simple (what is a context manager?) to complex (custom `__enter__`/`__exit__`).
- Includes at least one analogy and one code example.
- Does NOT assume the reader knows what `with` statements are at the start.

**Expected score range:** 65–85.

**Pass criteria:**
- [ ] The word "analogy" or a clear real-world comparison appears in the output.
- [ ] A code example with `__enter__` and `__exit__` is present and syntactically valid.
- [ ] The explanation starts simple and grows in complexity.

---

## Test 6: Stress Test (3 loops, high threshold)

**Purpose:** Confirm the loop runs for multiple iterations without crashing,
and that `best_draft.txt` correctly tracks the highest score.

**Command:**
```bash
python run.py \
    --goal "Write a comprehensive guide to Python decorators: what they are, how they work, three practical examples (logging, timing, access control), and when NOT to use them." \
    --max-loops 4 \
    --threshold 88 \
    --min-improvement 2
```

**What this does:** Sets a high threshold (88) that Bootstrap profile models (3B) will
rarely hit on the first loop, forcing 2–3 iterations. On the Serious Work profile
(14B), this threshold may be reached in 1–2 loops on well-specified goals.

**Expected behavior:**
- Pipeline runs at least 2 loop iterations.
- Score history shows improvement (e.g., 58 → 67 → 74 → 79).
- Loop stops at `max_loops` if threshold is never reached.
- `best_draft.txt` holds the version that scored highest (not the last version).
- `run_summary.json` shows `stop_reason: "max_loops (4) reached"` or `"passed"`.

**Total expected time:** 4–8 minutes on Bootstrap (3B); 15–30 minutes on Serious Work (14B).

**Pass criteria:**
- [ ] Pipeline completes all 4 loops without crashing.
- [ ] `run_summary.json` contains a `scores` list with 3–4 entries.
- [ ] `best_draft.txt` corresponds to the highest score in the list.
- [ ] Memory pressure stays green throughout (check Activity Monitor).

---

## Test 7: Bad Prompt Test (graceful failure)

**Purpose:** Confirm the system handles nonsense input without crashing.

**Command:**
```bash
python run.py \
    --goal "asdfjkl qwerty banana purple monkey dishwasher" \
    --max-loops 1 \
    --threshold 50
```

**Expected behavior:**
- Supervisor should still produce a `refined_goal` (it will try to interpret the input).
- Builder may produce an off-topic or confused response.
- Critic should note that the output does not address a coherent goal.
- Judge should score it low (likely 25–45).
- Pipeline completes without a Python exception.
- `run_summary.json` is written with `passed: false`.

**Pass criteria:**
- [ ] No Python traceback. Pipeline runs end-to-end.
- [ ] `run_summary.json` exists with a low score.
- [ ] `final_output.txt` exists (even if the content is confused).
- [ ] The system did NOT crash, hang indefinitely, or produce an unhandled exception.

---

## Test 8: Interrupt Recovery Test

**Purpose:** Confirm that `Control + C` mid-run saves partial output.

**Command:**
```bash
python run.py \
    --goal "Write a detailed guide to Python async/await with three code examples." \
    --max-loops 3 \
    --threshold 75
```

After the Builder finishes (you will see `[Builder] Draft complete`) but before
the Critic finishes, press `Control + C`.

**Expected behavior:**
- Terminal prints: `[INTERRUPTED] Run stopped by user.`
- Terminal prints: `Partial output saved to: runs/<timestamp>/`

**Pass criteria:**
- [ ] At minimum, `02_builder_draft_v0.txt` exists in the run folder.
- [ ] No corrupted or zero-byte files.
- [ ] Running `python run.py` again with a new goal works normally.

---

## Test 9: Model Quality Comparison Test

**Purpose:** Confirm that the Serious Work profile produces meaningfully better
output than the Bootstrap profile on the same goal. This test gives you evidence
that upgrading profiles is worth the longer runtime, and helps you calibrate
your quality expectations for each profile.

**Run the same prompt through Bootstrap, then Serious Work:**

```bash
# Bootstrap profile run
python run.py \
    --goal "Explain the trade-offs between SQL and NoSQL databases. Include when you would choose each, with one concrete real-world scenario for each choice." \
    --model-main llama3.2:3b \
    --model-fast llama3.2:3b \
    --max-loops 2 --threshold 60
```

Save the run folder name (shown in terminal output). Then immediately run:

```bash
# Serious Work profile run (same goal, same parameters)
python run.py \
    --goal "Explain the trade-offs between SQL and NoSQL databases. Include when you would choose each, with one concrete real-world scenario for each choice." \
    --model-main qwen2.5:14b \
    --model-fast llama3.1:8b \
    --max-loops 2 --threshold 70
```

**Compare the two runs side by side:**
```bash
# Replace timestamps with your actual run folder names
diff \
    runs/<bootstrap-timestamp>/final_output.txt \
    runs/<serious-timestamp>/final_output.txt
```

Or open both files in VS Code split view:
```bash
code runs/<bootstrap-timestamp>/final_output.txt \
       runs/<serious-timestamp>/final_output.txt
```

**What to evaluate:**

| Dimension | What to look for |
|-----------|-----------------|
| Specificity | Does the Serious output name actual technologies, give concrete numbers, or refer to named use cases? |
| Structure | Are sections clearly delineated and logically ordered? |
| Accuracy | Are the trade-offs described actually correct? |
| Usefulness | If you were making a real architectural decision, which output would you actually use? |
| Critique quality | Compare the two `loop01_critic.txt` files — does the Serious profile critic find more specific issues? |
| Score progression | Compare `run_summary.json` — what are the score histories? |

**Expected behavior:**
- Bootstrap: 3B model produces adequate output. Critique is less specific. Scores typically 45–65.
- Serious: 14B builder produces more thorough, structured output. Independent critic and judge provide more useful scores. Scores typically 65–82.

**The test passes if:**
- [ ] Both runs complete without errors.
- [ ] The Serious Work `final_output.txt` is noticeably more thorough and specific.
- [ ] The Serious Work critique (`loop01_critic.txt`) identifies more specific issues.
- [ ] The Serious Work judge score is more differentiated (not always 70–75).
- [ ] You can articulate which profile you would use for which type of task.

**If the outputs look similar:** This is a signal that the goal was too simple
for the quality difference to show. Try a more demanding goal:
```bash
--goal "Design a data model for a multi-tenant SaaS application that handles user permissions, audit logs, and soft deletes. Show the SQL schema and explain the key design decisions."
```
More complex goals show larger quality gaps between profiles.

---

# SECTION 22 — Git and GitHub Setup

## 22.1 Check if Git is installed and configured

```bash
git --version
```
Expected: `git version 2.x.x`

Check your identity configuration:
```bash
git config --global user.name
git config --global user.email
```

If either returns nothing, set them now:
```bash
git config --global user.name "Your Full Name"
git config --global user.email "your@email.com"
```
**What this does:** Saves your name and email in `~/.gitconfig`. These values
appear in every commit you make on this machine, on any project.

Set the default branch name to `main` (modern standard):
```bash
git config --global init.defaultBranch main
```

---

## 22.2 Initialize the local repository

Make sure you are in the project root:
```bash
cd ~/Downloads/multi-modal-workflow
pwd
```
Expected: `/Users/andyyaro/Downloads/multi-modal-workflow`

Initialize Git:
```bash
git init
```
**What this does:** Creates a hidden `.git/` folder that tracks all changes to
files in this directory. This is the local repository.

Verify it worked:
```bash
git status
```
You will see a long list of untracked files. That is correct — nothing is committed yet.

---

## 22.3 Verify your `.gitignore` is working

Before staging anything, confirm the right files are excluded:
```bash
git status --short
```

You should NOT see any of these:
- `.venv/` (entire virtual environment)
- `runs/` contents beyond `.gitkeep`
- `logs/` contents beyond `.gitkeep`
- `*.db` files
- `__pycache__/` folders
- `.DS_Store`

If you see `.venv/` listed, your `.gitignore` is not being applied. Check:
```bash
cat .gitignore | grep venv
```
Expected: `.venv/` should appear. If the file is empty, re-create it from Section 7.9.

---

## 22.4 Create the first commit

Stage every file that should be tracked (Git will skip anything in `.gitignore`):
```bash
git add .
```
**What this does:** Stages all unignored files for inclusion in the next commit.
The `.gitignore` file ensures `.venv/`, `runs/`, `logs/`, and `*.db` are excluded.

Review exactly what will be committed:
```bash
git status
```
Scan the list. If you see anything sensitive or large that should not be there,
add it to `.gitignore` and run `git add .` again before committing.

Make the first commit:
```bash
git commit -m "Initial commit: Local AI Orchestrator terminal MVP

- Full 7-agent pipeline: Supervisor → Planner → Builder → Critic → Fixer → Judge → Synthesizer
- Plain Python terminal runner (run.py) with reiteration loop
- LangGraph pipeline variant (run_langgraph.py)
- SQLite run history (orchestrator/database.py)
- Provider-agnostic model adapter layer (orchestrator/adapters.py)
- Workflow modes: writing, coding, planning, debugging, study
- Code verification with subprocess execution and pytest runner
- Streamlit dashboard (app/streamlit_app.py)
- Structured JSON logging (orchestrator/logger.py)
- Config-driven model assignment (config/models.yaml, config/modes.yaml)"
```

Verify the commit was created:
```bash
git log --oneline
```
Expected: one line showing your commit hash and message.

---

## 22.5 Create a GitHub repository

1. Go to https://github.com and sign in.
2. Click the **+** icon in the top-right corner → **New repository**.
3. Fill in:
   - **Repository name:** `multi-modal-workflow`
   - **Description:** `Local-first multi-agent AI orchestration system powered by Ollama. Runs entirely on a MacBook with no paid APIs.`
   - **Visibility:** Public (for portfolio) or Private (for now, make public later).
   - **Do NOT** check "Add a README file" — you already have one locally.
   - **Do NOT** add `.gitignore` — you already have one.
   - **Do NOT** add a license — you can add one later.
4. Click **Create repository**.
5. GitHub shows you a page with setup commands. Copy the URL shown — it looks like:
   `https://github.com/yourusername/multi-modal-workflow.git`

---

## 22.6 Connect local repo to GitHub and push

```bash
git remote add origin https://github.com/yourusername/multi-modal-workflow.git
```
**What this does:** Registers your GitHub repository as a remote called `origin`.
Replace `yourusername` with your actual GitHub username.

Verify the remote was added:
```bash
git remote -v
```
Expected:
```
origin  https://github.com/yourusername/multi-modal-workflow.git (fetch)
origin  https://github.com/yourusername/multi-modal-workflow.git (push)
```

Push your commit to GitHub:
```bash
git push -u origin main
```
**What this does:** Pushes the `main` branch to GitHub and sets `origin/main` as
the tracking branch. The `-u` flag means future `git push` commands (no arguments)
will push to this same place.

You will be prompted for your GitHub credentials. Use your GitHub username and a
**Personal Access Token** (PAT) as the password — GitHub no longer accepts your
account password for Git operations.

**To create a PAT:**
1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic).
2. Click **Generate new token (classic)**.
3. Set expiration to 90 days or No expiration.
4. Check scope: `repo` (full control of private repositories).
5. Click Generate. Copy the token — you cannot see it again.
6. Use this token as your password when `git push` prompts for credentials.

To avoid entering the token every time, store it in macOS Keychain:
```bash
git config --global credential.helper osxkeychain
```
After running this, the next `git push` will prompt you once, and macOS will
store the credentials securely.

**Verify:** Visit `https://github.com/yourusername/multi-modal-workflow` in your
browser. You should see your files listed.

---

## 22.7 What to include in commits going forward

Commit frequently — at least after each working phase:
```bash
# Good commit cadence examples:
git commit -m "Add LangGraph pipeline variant"
git commit -m "Add Streamlit dashboard with live agent output"
git commit -m "Add SQLite run history and show_history.py"
git commit -m "Add coding verification with subprocess runner and pytest"
git commit -m "Improve Judge prompt: fix score inflation pattern"
```

Push after each logical feature is working:
```bash
git push
```

---

## 22.8 What NOT to commit — security reminders

⚠️ **Never commit:**
- `.env` — may contain API keys.
- `runs/history.db` — contains your personal run data.
- Any file named `*_key*`, `*_secret*`, `*_token*`, `*_password*`.
- The `.venv/` folder — 50,000+ files that belong to pip, not your project.

Before every push, run:
```bash
git status
git diff --cached --name-only
```
Review the file list. If you see anything that looks sensitive, remove it
from staging with:
```bash
git restore --staged <filename>
```
And add it to `.gitignore` so it is never accidentally staged again.

---

## 22.9 How to make the project look professional on GitHub

**Write a strong README** (see Section 23 for the full outline).

**Add a topics/tags to the repo:**
On your GitHub repository page → click the gear icon next to "About" →
add topics: `python`, `ollama`, `llm`, `langgraph`, `streamlit`, `local-ai`,
`multi-agent`, `machine-learning`.

**Pin the repository to your profile:**
On your GitHub profile page → click "Customize your pins" → select
`multi-modal-workflow`.

**Add a screenshot to the README** (once Streamlit works):
```bash
# Take a screenshot of the Streamlit UI (Command + Shift + 4, drag to select)
# Save it as: docs/screenshot_dashboard.png
mkdir -p docs
# Then drag the screenshot file into the docs/ folder in Finder
git add docs/screenshot_dashboard.png
git commit -m "Add dashboard screenshot to docs/"
git push
```
In your README, reference it:
```markdown
![Dashboard screenshot](docs/screenshot_dashboard.png)
```

---

# SECTION 23 — Final README Outline

Create the README file:
```bash
code README.md
```

Use this outline and content:

```markdown
# Local AI Orchestrator

> A local-first, free-to-run multi-agent AI pipeline that improves outputs
> through structured critique, revision, scoring, and final synthesis.
> Runs entirely on a MacBook Pro with no paid APIs. No internet connection required after setup.

---

## The Problem

Single-call AI responses are inconsistent. You send one prompt, get one answer,
and have no way to know if it is the best possible output or a mediocre first
draft. Large AI companies solve this with internal feedback loops and verification
systems — but those are invisible to users and require expensive API calls.

This project brings that quality loop to your local machine: one goal in,
multiple rounds of critique and revision, a scored verdict, and a polished
final output — all running free on your own hardware.

---

## Features

- **7-agent quality pipeline**: Supervisor → Planner → Builder → Critic →
  Fixer → Judge → Synthesizer
- **Scored reiteration loop**: Output improves across up to N iterations until
  it passes a quality threshold (configurable)
- **Structured JSON scoring**: The Judge returns category scores, pass/fail,
  hard fails, and rationale on every iteration
- **6 workflow modes**: Writing, Coding, Planning, Debugging, Study, General —
  each with adapted prompts and scoring rubrics
- **Real code verification**: In coding mode, generated Python is executed and
  pytest tests are run; failures are fed back into the loop
- **Streamlit dashboard**: Local web UI with live agent output, score chart,
  and run history browser
- **SQLite run history**: Every run is saved locally with full intermediate steps
- **Provider-agnostic design**: Ollama is the default; the adapter layer supports
  adding OpenAI or Anthropic without changing agent code
- **Fully local and free**: No API keys, no internet connection after setup, no subscription

---

## Architecture

```
User Goal
    │
    ▼
┌─────────────┐
│  Supervisor │  Refines the goal and determines workflow mode
└──────┬──────┘
       │
    ▼
┌─────────────┐
│   Planner   │  Creates a structured plan for the Builder to follow
└──────┬──────┘
       │
    ▼
┌─────────────┐
│   Builder   │  Writes the first complete draft
└──────┬──────┘
       │
    ┌──▼──────────────────────────────────────┐
    │           IMPROVEMENT LOOP              │
    │                                         │
    │  ┌─────────┐   ┌───────┐   ┌───────┐   │
    │  │  Critic │──▶│ Fixer │──▶│ Judge │   │
    │  └─────────┘   └───────┘   └───┬───┘   │
    │       ▲                        │        │
    │       └──── score < threshold ─┘        │
    └──────────────────────────────────────────┘
       │
    score ≥ threshold OR max loops reached
       │
    ▼
┌──────────────┐
│ Synthesizer  │  Polishes the best-scoring draft into the final output
└──────┬───────┘
       │
    ▼
 Final Output + SQLite history + saved run files
```

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Local model runtime | [Ollama](https://ollama.com) |
| Pipeline orchestration | [LangGraph](https://github.com/langchain-ai/langgraph) |
| Web dashboard | [Streamlit](https://streamlit.io) |
| Run history | SQLite (Python standard library) |
| Language | Python 3.12+ |
| Models used | llama3.2:3b (Bootstrap) · qwen2.5:14b + phi4:14b (Serious Work) |

---

## Hardware Requirements

- Apple Silicon Mac (M1/M2/M3) with 16GB+ unified memory
- Tested on: MacBook Pro M3, 24GB RAM, macOS 15+
- No GPU required — Apple Silicon handles inference natively
- No internet connection required after models are downloaded

---

## Setup

### 1. Install Ollama

Download from https://ollama.com/download and install the macOS app.

### 2. Pull the models

> **Verify tags before pulling** — run `ollama search <name>` and use the exact
> tag shown in the output. Tags in this README were correct at time of writing
> but may change between Ollama releases.

Start with the Bootstrap profile (fast, minimal RAM):

```bash
ollama pull llama3.2:3b
```

Once the pipeline is verified end-to-end, upgrade to the Serious Work profile
(see `config/models.yaml` and Section 6 of the build guide):

```bash
ollama pull llama3.1:8b
ollama pull qwen2.5:14b
ollama pull gemma3:12b
ollama pull phi4:14b
```

Then set `active_profile: serious` in `config/models.yaml`.

### 3. Clone and set up Python environment

```bash
git clone https://github.com/yourusername/multi-modal-workflow.git
cd multi-modal-workflow
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Run the terminal pipeline

```bash
python run.py --goal "Your goal here"
```

### 5. Launch the Streamlit dashboard

```bash
streamlit run app/streamlit_app.py
# Open http://localhost:8501 in your browser
```

---

## Example Run

```
Goal: Explain how Python decorators work with three practical examples.

[Supervisor]  Mode: study
[Planner]     Created 5-step explanation plan
[Builder]     Draft v0: 612 chars
[Critic]      Found 4 issues: missing timing example, no analogy, intro too brief
[Fixer]       Revision 1: 891 chars
[Judge]       Score: 74/100 — PASS (threshold: 70)
[Synthesizer] Final output: 944 chars

Stop reason : passed (score 74 ≥ threshold 70)
Loops run   : 1 / 3
Time elapsed: 87s
```

---

## Screenshots

*Dashboard screenshots coming soon.*

<!-- Add after Streamlit UI is complete:
![Dashboard](docs/screenshot_dashboard.png)
![Score progression](docs/screenshot_scores.png)
-->

---

## Configuration

Edit `config/models.yaml` to change models without touching Python code.
Switch `active_profile` to move between the four quality levels:

```yaml
provider: ollama
active_profile: bootstrap   # bootstrap | serious | coding | fast

profiles:
  bootstrap:
    builder: "llama3.2:3b"
    judge:   "llama3.2:3b"
    # ... all 7 roles → llama3.2:3b
  serious:
    builder: "qwen2.5:14b"
    judge:   "phi4:14b"     # different family → independent verdict
    critic:  "gemma3:12b"   # third family
    # ... (see Section 18.2 for full config)
```

Edit `config/modes.yaml` to adjust per-mode prompts and scoring weights.

---

## Limitations

- Response quality is bounded by the active model profile (Bootstrap: 3B; Serious Work: 14B)
- Each pipeline run takes 1–8 minutes depending on model size and loop count
- Code verification runs generated code locally — review safety notes before
  using on untrusted goals (see `orchestrator/code_runner.py`)
- The Judge's scoring is model-dependent and may not be perfectly calibrated
- No multi-user support — designed for single-user local use only

---

## Planned Improvements

- [ ] Add a RAG layer using `nomic-embed-text` for context retrieval from past runs
- [ ] Support streaming output in the Streamlit dashboard
- [ ] Add a diff view showing changes between each revision
- [ ] Optional OpenAI / Anthropic provider via config switch
- [ ] Export final outputs as formatted PDF or Markdown files
- [ ] Add a "compare runs" view to the history panel

---

## Safety Notes

- This project runs entirely locally. No data is sent to external servers.
- In coding mode, generated Python code is executed on your machine.
  Review `orchestrator/code_runner.py` for the safety blocklist.
- Never add API keys or secrets to files tracked by Git.
- The `.gitignore` excludes `.env`, `runs/`, and `logs/` by default.

---

## License

MIT License — see `LICENSE` file.

---

*Built with Ollama, LangGraph, Streamlit, and Python on Apple Silicon.*
```

Save the README:
```bash
git add README.md
git commit -m "Add README with architecture diagram and setup instructions"
git push
```

---

# SECTION 24 — Build Timeline

This is a realistic 7-day schedule for someone working 2–4 hours per day.
Each day has a clear goal, concrete tasks, and a "done" definition so you
know when to stop for the day rather than over-engineering.

---

## Day 1 — Foundations

**Goal:** Verify all tools work. Pull models. Confirm Python-to-Ollama communication.

**Tasks:**
1. Run all verification commands from Section 3 and fix any failures.
2. Start Ollama and confirm it is running (`curl http://localhost:11434`).
3. Pull the Bootstrap profile model (Section 6.7 — the one-command pull sequence).
4. Create the full project folder structure (Section 7).
5. Create the virtual environment and install `requests` and `pyyaml`.
6. Write and run `test_ollama.py` (Section 8).
7. Initialize Git and make the first commit.

**Commands to run by end of Day 1:**
```bash
ollama pull llama3.2:3b            # Bootstrap profile — all 7 roles
python test_ollama.py              # prints a model response
git log --oneline                  # shows first commit
ollama list                        # shows llama3.2:3b
```

**What "done" looks like:**
`test_ollama.py` runs without errors. A coherent model response prints to terminal.
Git has one commit. Project folder has all subfolders and placeholder files.

**Backup plan if stuck:**
If `llama3.2:3b` inference is too slow (>60 s/response), try `llama3.2:1b` for
Day 1 sanity checks — it's smaller and faster. Restore `3b` on Day 2.
If pip install fails, try Python 3.12 (Section 5.9) before Day 2.

---

## Day 2 — Two-Agent Loop

**Goal:** Builder → Critic pipeline working. First real agent-to-agent handoff.

**Tasks:**
1. Write `agents/base_agent.py` (Section 9.1).
2. Write `agents/builder.py` and `agents/critic.py` (Sections 9.2–9.3).
3. Write `prompts/builder.txt` and `prompts/critic.txt` (Section 9.4).
4. Write `run_phase2.py` (Section 9.5).
5. Run the two-agent pipeline on three different goals.
6. Read the saved critique files. Is the feedback specific? If not, improve the
   Critic prompt.
7. Commit working code.

**Commands to run by end of Day 2:**
```bash
python run_phase2.py --goal "Explain what recursion means in programming."
cat runs/$(ls -t runs/ | head -1)/02_critic_review.txt
```

**What "done" looks like:**
Builder produces a substantive draft (200+ words). Critic produces numbered,
specific issues. Two files saved per run. No errors.

**Backup plan:**
If the Critic is still vague after prompt improvements, confirm both agents are
on Bootstrap (`llama3.2:3b`) and iterate faster on the prompt. The Bootstrap
profile is intentionally fast for exactly this kind of prompt tuning.

---

## Day 3 — Fixer, Judge, and Reiteration Loop

**Goal:** Full terminal MVP working end-to-end.

**Tasks:**
1. Write `agents/fixer.py`, `agents/judge.py` (Sections 10.1–10.2).
2. Write `prompts/fixer.txt` and `prompts/judge.txt` (Section 10.3).
3. Write `run_phase3.py` and test it (Section 10.4–10.5).
4. Write `agents/supervisor.py`, `agents/planner.py`, `agents/synthesizer.py`.
5. Write remaining prompt templates (supervisor, planner, synthesizer).
6. Write `run.py` with the full reiteration loop (Section 11.4).
7. Run the full pipeline end-to-end. Confirm loop, scoring, and stop logic.
8. Run the stress test (Section 21, Test 6) to confirm multi-loop stability.
9. Commit.

**Commands to run by end of Day 3:**
```bash
python run.py --goal "Write a guide to Python list comprehensions." --max-loops 3
cat runs/$(ls -t runs/ | head -1)/run_summary.json
```

**What "done" looks like:**
`run.py` runs end-to-end. `run_summary.json` shows a valid score history.
`final_output.txt` contains polished prose. Loop stops for the right reason.

**Backup plan:**
If the Judge JSON never parses correctly on Bootstrap, add the "first char must be
{" instruction to `prompts/judge.txt`. If parsing remains flaky, switch to the
Serious Work profile — `phi4:14b` (Judge) is significantly more reliable for
structured JSON output. Run `--max-loops 1` until parsing is stable, then increase.

---

## Day 4 — LangGraph + Config System

**Goal:** LangGraph variant working. Config-driven model assignment in place.

**Tasks:**
1. Install `langgraph langchain-ollama langchain-core`.
2. Write `orchestrator/state.py` and `orchestrator/graph.py` (Section 12.5–12.6).
3. Write `run_langgraph.py` (Section 12.7).
4. Run the same goal through both `run.py` and `run_langgraph.py`.
   Compare the outputs — they should be equivalent.
5. Write `orchestrator/adapters.py` and `orchestrator/config_loader.py`
   (Sections 18.3–18.4).
6. Update `BaseAgent.call_model()` to use the adapter.
7. Write `config/models.yaml` final version (Section 18.2).
8. Write `config/modes.yaml` (Section 15.2).
9. Write `orchestrator/modes.py` (Section 15.3).
10. Wire mode prompt suffixes into Builder and Judge (Section 15.4).
11. Commit.

**What "done" looks like:**
`run_langgraph.py --goal "..."` produces the same quality output as `run.py`.
Changing `active_profile` in `config/models.yaml` from `bootstrap` to `serious`
(after pulling the Serious Work models from Section 6.7) upgrades all 7 agent
models without editing Python files.

**Day 4 model upgrade checkpoint:**
Once the LangGraph pipeline passes end-to-end with Bootstrap models, pull the
Serious Work profile and switch `active_profile: serious`. Rerun the same goal
and compare output quality — this is the point where the pipeline starts
producing genuinely useful work.

**Backup plan:**
If LangGraph has import errors on Python 3.14, use Python 3.12 (Section 5.9).
If the graph logic is confusing, keep `run.py` as the primary runner and return
to the LangGraph variant later. The plain Python version is fully functional.

---

## Day 5 — SQLite History + Logging + Coding Verification

**Goal:** Data persistence working. Coding mode verified with real execution.

**Tasks:**
1. Write `orchestrator/database.py` (Section 14.3).
2. Integrate database save into `run.py` (Section 14.4).
3. Write `show_history.py` (Section 14.5).
4. Run 3 pipeline runs on different goals and verify history is saved:
   ```bash
   $ python show_history.py
   $ python show_history.py --stats
   ```
5. Write `orchestrator/logger.py` (Section 19.1).
6. Wire logging into `run.py` (Section 19.2).
7. Write `orchestrator/code_runner.py`, `orchestrator/linter.py`,
   `orchestrator/verifier.py` (Sections 16.3–16.7).
8. Run the coding test (Section 21, Test 3).
9. Commit.

**What "done" looks like:**
`show_history.py` shows a table of at least 3 past runs.
`logs/pipeline.log` contains JSON entries for every run.
A coding goal produces `loop01_code_run.txt` showing execution results.

---

## Day 6 — Streamlit Dashboard

**Goal:** Local web UI running with live output and history panel.

**Tasks:**
1. Install `streamlit`.
2. Write `app/streamlit_app.py` (Section 13.3).
3. Add the run history panel to the Streamlit app (Section 14.6).
4. Run `streamlit run app/streamlit_app.py` and open the browser.
5. Run all 8 system tests from Section 21 (some via the Streamlit UI).
6. Fix any UI bugs (check Section 13.7 for common issues).
7. Take a screenshot of the working dashboard.
8. Save the screenshot to `docs/` and add to `README.md`.
9. Write the full README (Section 23).
10. Commit and push to GitHub.

**What "done" looks like:**
Streamlit UI opens at `http://localhost:8501`. Running a goal from the browser
shows live agent output, a score chart, and the final result. Run history panel
shows past runs. README on GitHub shows the architecture diagram and setup steps.

---

## Day 7 — Polish, Tests, and Portfolio Readiness

**Goal:** Everything tested, documented, and professionally presented on GitHub.

**Tasks:**
1. Write formal test files in `tests/`:
   ```bash
   $ code tests/test_judge_parsing.py
   $ code tests/test_code_runner.py
   $ code tests/test_database.py
   ```
2. Run all tests:
   ```bash
   $ pytest tests/ -v
   ```
3. Run the full test plan from Section 21.
4. Fix any remaining failures.
5. Review every prompt template — improve any that produced weak output.
6. Review `config/models.yaml` — confirm model assignments are optimal.
7. Run `ruff check .` and fix any lint issues:
   ```bash
   $ ruff check . --fix
   ```
8. Final commit with version tag:
   ```bash
   $ git add .
   $ git commit -m "v1.0.0: Complete terminal MVP + Streamlit dashboard"
   $ git tag v1.0.0
   $ git push && git push --tags
   ```
9. Make the GitHub repository public (if it was private).
10. Add the project to your GitHub profile pins.

**What "done" looks like:**
- `pytest tests/ -v` passes all tests.
- `python run.py --goal "..."` runs in under 3 minutes for a 1-loop run.
- The GitHub repository has a README with screenshots, architecture diagram,
  and clear setup instructions.
- The project is pinned on your GitHub profile.

---

# SECTION 25 — Final Checklist

Use this checklist to track your progress. Check each box as you complete it.
Do not move to the next phase until the current phase checklist is complete.

---

## Phase 0: Existing Setup Verification

- [ ] `brew --version` returns a version number
- [ ] `python3 --version` returns Python 3.14.x or 3.12.x
- [ ] `pip3 --version` references the correct Python version
- [ ] `git --version` returns a version number
- [ ] `git config --global user.name` returns your name
- [ ] `git config --global user.email` returns your email
- [ ] `code --version` returns a VS Code version
- [ ] `ollama --version` returns the CLI version (warning is OK)
- [ ] `curl http://localhost:11434` returns `Ollama is running`

---

## Phase 1: Ollama

> **Before any pull:** run `ollama search <model-name>` and confirm the exact tag.
> Tags in this guide were correct at time of writing but may change between Ollama
> releases. Use whatever tag `ollama search` shows — not the tag from memory.

- [ ] Ollama app starts without errors (llama icon in menu bar)
- [ ] `ollama list` runs without errors
- [ ] `ollama search llama3.2` confirms tag, then `ollama pull llama3.2:3b` completes
- [ ] `ollama run llama3.2:3b "hello"` returns a response within 30 seconds
- [ ] `curl http://localhost:11434` returns `Ollama is running` while app is open
- [ ] `OLLAMA_KEEP_ALIVE=5m` is set in `~/.zshrc`

---

## Phase 2: Models

- [ ] `ollama list` shows `llama3.2:3b` (Bootstrap profile minimum)
- [ ] Bootstrap model responds within 30 seconds on first call
- [ ] Memory pressure stays green during model inference (Activity Monitor)
- [ ] `config/models.yaml` has `active_profile: bootstrap` and a `profiles:` block
- [ ] `config/models.yaml` maps all 7 roles under the `bootstrap` profile
- [ ] Switching `active_profile` to `serious` (after pulling those models) works
- [ ] `ollama rm` can cleanly remove a model if needed

---

## Phase 3: Python Environment

- [ ] `.venv/` exists inside the project directory
- [ ] `source .venv/bin/activate` changes the prompt to show `(.venv)`
- [ ] `which python` shows the `.venv` path when environment is active
- [ ] `pip install -r requirements.txt` completes without errors
- [ ] `python -c "import requests, yaml; print('OK')"` prints OK
- [ ] VS Code shows the `.venv` interpreter in the status bar
- [ ] `activate.sh` runs correctly and prints the Python version
- [ ] `requirements-lock.txt` exists (run `pip freeze > requirements-lock.txt`)

---

## Phase 4: Terminal MVP

- [ ] `python test_ollama.py` prints a model response
- [ ] All 9 `agents/*.py` files exist and are non-empty
- [ ] All 7 `prompts/*.txt` files exist and contain system prompts
- [ ] `python run_phase2.py --goal "test"` saves files to `runs/`
- [ ] `python run_phase3.py --goal "test"` returns a valid Judge JSON verdict
- [ ] `python run.py --goal "test" --max-loops 1 --threshold 40` completes
- [ ] `python run.py --goal "test" --max-loops 3 --threshold 80` runs 2+ loops
- [ ] `best_draft.txt` tracks the highest-scoring version correctly
- [ ] `run_summary.json` contains accurate score history and stop reason
- [ ] `final_output.txt` is non-empty and polished
- [ ] `Control + C` during a run saves partial output without crashing

---

## Phase 5: LangGraph

- [ ] `pip install langgraph langchain-ollama langchain-core` succeeds
- [ ] `python -c "from langgraph.graph import StateGraph; print('OK')"` prints OK
- [ ] `orchestrator/state.py` defines `PipelineState` TypedDict
- [ ] `orchestrator/graph.py` builds a compiled StateGraph
- [ ] `python run_langgraph.py --goal "test"` completes end-to-end
- [ ] LangGraph output quality matches `run.py` output for same goal
- [ ] `run.py` (plain Python fallback) still works alongside LangGraph version

---

## Phase 6: Streamlit

- [ ] `pip install streamlit` succeeds
- [ ] `streamlit run app/streamlit_app.py` opens browser at `localhost:8501`
- [ ] Entering a goal and clicking Run starts the pipeline
- [ ] Agent output sections appear as pipeline runs
- [ ] Score chart updates after each Judge verdict
- [ ] Final output displays with download button
- [ ] Run summary shows score, pass/fail, and loop count
- [ ] Files are saved to `runs/ui_<timestamp>/` correctly
- [ ] `Control + C` stops the Streamlit server cleanly

---

## Phase 7: SQLite

- [ ] `orchestrator/database.py` exists with `init_db()`, `save_run()`, `load_all_runs()`
- [ ] After a `run.py` run, `runs/history.db` is created
- [ ] `python show_history.py` displays at least one run in the table
- [ ] `python show_history.py --run-id 1` shows full details for run #1
- [ ] `python show_history.py --stats` shows total runs and average score
- [ ] History panel in Streamlit shows past runs
- [ ] `runs/history.db` is excluded from Git (check with `git status`)
- [ ] `cp runs/history.db runs/history_backup.db` creates a backup successfully

---

## Phase 8: Testing

- [ ] Writing test (Section 21, Test 1) passes all criteria
- [ ] Planning test (Section 21, Test 2) produces structured week-by-week output
- [ ] Coding test (Section 21, Test 3) produces runnable code with passing pytest
- [ ] Debugging test (Section 21, Test 4) identifies correct root cause
- [ ] Study test (Section 21, Test 5) includes analogy and code example
- [ ] Stress test (Section 21, Test 6) runs 4 loops without crash or memory pressure
- [ ] Bad prompt test (Section 21, Test 7) completes without Python exception
- [ ] Interrupt test (Section 21, Test 8) saves partial output on Ctrl+C

---

## Phase 9: GitHub

- [ ] `git init` has been run in the project directory
- [ ] `.gitignore` correctly excludes `.venv/`, `runs/`, `logs/`, `*.db`, `.env`
- [ ] `git status` shows no sensitive or unwanted files staged
- [ ] First commit exists: `git log --oneline` shows at least one entry
- [ ] GitHub repository created at `github.com/yourusername/multi-modal-workflow`
- [ ] `git remote -v` shows `origin` pointing to the GitHub URL
- [ ] `git push -u origin main` succeeds
- [ ] Repository is visible on GitHub with all source files
- [ ] `README.md` is visible on the GitHub repository homepage
- [ ] README contains: problem statement, features, architecture, setup steps
- [ ] Repository has relevant topics/tags added (python, ollama, langgraph, etc.)
- [ ] Repository is pinned on your GitHub profile

---

## Troubleshooting Checklist (if anything breaks)

- [ ] Ollama running? → `curl http://localhost:11434`
- [ ] Virtual environment active? → prompt shows `(.venv)`
- [ ] Running from project root? → `pwd` shows project path
- [ ] Model downloaded? → `ollama list`
- [ ] Memory pressure? → Activity Monitor → Memory tab → green?
- [ ] Prompt templates exist? → `ls prompts/` shows all 7 `.txt` files
- [ ] Config files exist? → `ls config/` shows `models.yaml` and `modes.yaml`
- [ ] Runs folder writable? → `ls -la runs/` shows read/write permissions
- [ ] Logs folder writable? → `ls -la logs/`
- [ ] Judge JSON malformed? → Check `raw_judge_output` in judge JSON file
- [ ] Loop not stopping? → Check `min_improvement` and `max_loops` flags
- [ ] Code verification failing? → Check `loop01_code_run.txt` for error details
- [ ] Streamlit import error? → Run from project root, not from `app/` subfolder
- [ ] GitHub push rejected? → Use PAT, not account password; check remote URL

---

## Final Sign-Off

You have a complete, portfolio-ready local AI orchestration system when:

- [ ] `python run.py --goal "Explain what a REST API is with a Python example."` completes
  in under 5 minutes and produces a polished, accurate explanation.
- [ ] `streamlit run app/streamlit_app.py` opens a working dashboard that shows
  live agent output, scores, and run history.
- [ ] `python show_history.py` shows at least 5 past runs.
- [ ] The GitHub repository has a README that clearly explains what the project
  does and how to set it up on a new machine.
- [ ] You can explain to someone else what each of the 7 agents does and why
  the loop exists.

**Congratulations — you built a serious local AI system from scratch.**

---

*End of the Local AI Orchestrator Build Guide.*
*Total sections: 25 | Complete build manual for MacBook Pro M3 · 24GB RAM · Ollama · Python · LangGraph · Streamlit · SQLite*
