# 04 — Optional Self-Hosted MacBook Runner (Track B)

## 4.1 What this section covers

This section defines **Track B**: an optional, manually-triggered
`.github/workflows/macbook-acceptance.yml` that runs on your own MacBook
instead of a GitHub-hosted server. This is the *design and reference* for
that workflow, plus the safety rules around it. It is optional — you can
complete the entire v1.1 roadmap using only Track A (Chunk 2's other file)
and manual testing. Set this up only when you specifically want automated
real-hardware acceptance checks.

## 4.2 What a self-hosted runner actually is

A GitHub Actions "runner" is just a background process that listens for jobs
GitHub assigns to it and executes them. A GitHub-hosted runner is a fresh
Linux (or macOS/Windows) virtual machine GitHub spins up per job and destroys
afterward. A **self-hosted runner** is the same idea, except the process runs
on a machine you control — in this case, your MacBook Pro — and it does not
get destroyed after each job. It has access to whatever is already on that
machine: your real Ollama installation, your real pulled models, your real
24GB of unified memory, your real filesystem.

This matters because it's the only way to answer "does this actually work on
my Mac" from an automated workflow, rather than from you manually running
`python run.py` yourself.

## 4.3 What Track B can validate that Track A cannot

- Ollama is actually installed and reachable (`curl http://localhost:11434`).
- `ollama list` shows the models the pipeline expects.
- A real small-model smoke run (e.g. `llama3.2:3b`) completes and produces
  the expected artifacts.
- Real wall-clock runtime, so you can catch a regression back toward the
  12m49s problem before it becomes a habit.
- Real memory behavior under your actual profile configuration (Phase 6).
- That no cloud call happened during a run where cloud fallback should be
  off by default (Phase 7) — this can only be verified against a real run,
  not a mock.

## 4.4 Security risks a self-hosted runner introduces — read before setting this up

⚠️ **This is the single riskiest piece of infrastructure in this whole guide.**
A self-hosted runner executes whatever code is in the workflow file, on a
branch that triggered it, on your real machine, with your real filesystem
access. GitHub's own documentation warns against using self-hosted runners
with public repositories for exactly this reason: anyone who can open a pull
request against a public repo could, in principle, get arbitrary code
executed on the machine running the runner, unless you explicitly gate it.

Hard rules for this project:

- **Never** configure this workflow to trigger on `pull_request` from a
  fork. Only trigger on `workflow_dispatch` (a button you click yourself) or,
  at most, `push` to branches you control directly in this repo.
- **Never** run untrusted pull request code on the MacBook runner. If this
  repo ever becomes genuinely public-collaborative, disable the self-hosted
  workflow for external PRs entirely, or require a maintainer to manually
  approve each external-PR run.
- **Keep secrets out of logs.** If a cloud API key ever needs to exist on
  your Mac for a manual Phase 7 test, it lives in `.env` (already
  git-ignored) — never printed in a workflow step, never echoed to stdout.
- **Never let this workflow run destructive commands.** No `rm -rf`, no
  `git clean -xdf`, no writing outside the repo's own `runs/`/`logs/`
  directories.
- **Never let this workflow download large models automatically.** Model
  pulls stay a manual `ollama pull <model>` you type yourself, confirmed
  before the workflow references that model.
- **Never let this workflow enable cloud providers.** `config/models.yaml`'s
  `provider:` field stays `ollama` for every automated acceptance run.

## 4.5 When to use Track B, and when not to

**Use it when:** you've made a change to routing, timeouts, model profiles,
or anything that could plausibly change real runtime or real memory
behavior, and you want a repeatable, automated way to re-check that on your
actual Mac before merging.

**Do not use it when:** you just changed a validator's regex, a log message,
or a docstring — run the specific unit test locally instead; spinning up a
full acceptance run for a pure-Python change wastes your own machine's time
for no new information.

**Never use it for:** anything triggered by a pull request you did not open
yourself.

## 4.6 Setting up the runner itself

⚠️ GitHub's exact steps for registering a self-hosted runner (the download
URL, the registration token, the `config.sh` command) change over time and
are tied to your specific repository. Do not hardcode a token or URL from
this guide — go to your repo's **Settings → Actions → Runners → New
self-hosted runner** in GitHub's own UI and follow the current instructions
shown there for macOS/arm64. Treat any command GitHub gives you there as
one-time-use; registration tokens expire quickly and are not meant to be
reused or committed anywhere.

General shape of what you'll do (verify exact commands against GitHub's live
instructions when you get there):

- Download the macOS arm64 runner package GitHub's UI links to.
- Extract it into a dedicated folder outside this repo (for example,
  `~/actions-runner/`) — do not put runner binaries inside
  `/Users/andyyaro/Downloads/local-ai-orchestrator`.
- Run the configuration script GitHub's UI shows you, pointing it at this
  repository.
- Run the runner as a foreground process when you intend to use it, or
  install it as a background service only if you understand it will then
  listen for jobs continuously.

## 4.7 The `macbook-acceptance.yml` reference design

```yaml
name: MacBook Acceptance (manual)

on:
  workflow_dispatch:
    inputs:
      run_14b_smoke_test:
        description: "Also run the larger 14B model smoke test"
        type: boolean
        default: false

jobs:
  acceptance:
    runs-on: [self-hosted, macOS, arm64]
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Confirm Ollama is running
        run: curl --fail http://localhost:11434

      - name: List installed models
        run: ollama list

      - name: Install Python dependencies
        run: |
          python3 -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Small-model pipeline smoke test
        run: |
          python run.py \
            --goal "Write a 50-word summary of why sleep matters." \
            --model-main llama3.2:3b \
            --model-fast llama3.2:3b \
            --max-loops 1 \
            --threshold 50

      - name: Optional 14B smoke test
        if: ${{ inputs.run_14b_smoke_test == true }}
        run: |
          python run.py \
            --goal "Write a Python function that reverses a string, with one pytest test." \
            --model-main qwen2.5-coder:14b \
            --model-fast llama3.2:3b \
            --max-loops 1 \
            --threshold 60

      - name: Verify run artifacts exist
        run: |
          latest_run=$(ls -td runs/*/ | head -1)
          test -f "${latest_run}run_summary.json"
          test -f "${latest_run}final_output.txt"

      - name: Confirm no cloud provider was used
        run: |
          grep -q 'provider: ollama' config/models.yaml
```

Notes on this design:

- **`on.workflow_dispatch` only** — no `push`, no `pull_request`. This
  workflow only ever runs when you personally click "Run workflow" in
  GitHub's UI (or trigger it via `gh workflow run`), matching the "manual
  trigger only" rule from the master goals.
- **`run_14b_smoke_test` defaults to `false`.** The larger model test only
  runs when you explicitly opt in for that run, keeping ordinary acceptance
  checks fast and light on memory.
- **No step ever calls `ollama pull`.** If `ollama list` doesn't show a
  model this workflow needs, the job should fail loudly rather than silently
  downloading gigabytes onto your machine.
- **The final step is a cheap, explicit proof that cloud fallback stayed
  off** — it greps `config/models.yaml` for `provider: ollama`. Once Phase 7
  exists, this step should be extended to also check that the `cloud_calls`
  table (or equivalent log) recorded zero calls for this run.
- **Runtime threshold check is intentionally left out of this first version.**
  Add it once Phase 5 (metrics) gives you a reliable `run_summary.json` field
  to assert against, rather than parsing fragile stdout text.

## 4.8 Rollback

If this workflow ever misbehaves (hangs, runs something unexpected, or you
simply want to stop automated jobs from touching your Mac):

Stop the runner process immediately (Ctrl-C if running in foreground, or via
the service manager if installed as a background service).

Disable the workflow from running again without deleting your work:

```bash
git rm .github/workflows/macbook-acceptance.yml
git commit -m "chore: disable macbook acceptance workflow"
```

⚠️ This is a reversible, low-risk rollback — it only removes the workflow
definition, not the runner registration itself. To fully remove the runner
from GitHub, use the same Settings → Actions → Runners page you used to add
it.

## Verification

Verify:

```bash
curl --fail http://localhost:11434
```

```bash
ollama list
```

Expected result: Ollama responds, and the models this workflow references
(at minimum `llama3.2:3b`) are already present.

If it fails: do not have the workflow install or pull anything automatically
— start Ollama yourself (`open -a Ollama`) and pull any missing model
yourself before triggering the workflow.

Done when:

```text
Ollama is confirmed running, a self-hosted runner is registered against
this repo (only if you chose to set one up), and macbook-acceptance.yml
only ever triggers via workflow_dispatch — never on pull_request or push
from branches you don't control.
```

Commit suggestion (once you actually add the file):

```text
ci: add optional manual-trigger MacBook acceptance workflow
```
