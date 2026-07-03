# Local AI Orchestrator

A local-first multi-agent AI orchestration system designed to run structured AI workflows on a MacBook Pro M3 with 24GB unified memory.

The goal is to create a serious local workflow where one user prompt passes through specialized agents:

```text
Supervisor → Planner → Builder → Critic → Fixer → Judge → Final Synthesizer
```

The system is designed to run through Ollama using local models, with no paid API dependency by default. After initial setup, dependency installation, and model downloads, the workflow can run locally.

## Project Status

This repository is currently in the planning and build-documentation phase.

The first artifact is the full implementation guide:

- [`LOCAL_AI_ORCHESTRATOR_BUILD_GUIDE.md`](./LOCAL_AI_ORCHESTRATOR_BUILD_GUIDE.md)

## Target Stack

- macOS
- Ollama
- Python
- LangGraph
- Streamlit
- SQLite
- Local open-weight models

## Architecture

The orchestrator is designed around a sequential multi-agent workflow:

1. **Supervisor** — cleans and routes the user's goal
2. **Planner** — creates the execution plan
3. **Builder** — produces the first draft or implementation
4. **Critic** — identifies weaknesses and missing pieces
5. **Fixer** — revises the output based on critique
6. **Judge** — scores the result against a rubric
7. **Final Synthesizer** — polishes the best version

## Model Strategy

The system is designed around multiple model profiles:

- **Bootstrap Profile** — fast local model for testing the pipeline
- **Serious Work Profile** — stronger local models for real outputs
- **Coding Specialist Profile** — code-focused models for coding and debugging
- **Fast Profile** — low-memory fallback for quick testing

## Build Philosophy

This project prioritizes:

- local-first execution
- no paid APIs by default
- sequential model execution for 24GB unified memory
- role-specific agents
- iterative critique and revision loops
- beginner-friendly implementation
- clean documentation and reproducibility

## Next Milestones

- [ ] Verify local tools
- [ ] Start Ollama
- [ ] Set up Python virtual environment
- [ ] Pull Bootstrap model
- [ ] Build first local model call
- [ ] Build terminal MVP
- [ ] Add full agent loop
- [ ] Add model profiles
- [ ] Add Streamlit dashboard
- [ ] Add SQLite run history
