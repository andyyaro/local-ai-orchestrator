"""
coding_agent/

Phase 11 — a small, local coding-agent loop (read repo, propose a
constrained patch, run tests, stop when they pass), inspired by publicly
documented patterns from tools like Claude Code, SWE-agent, Aider, and
OpenHands.

This is the highest-risk subsystem in the project: it writes to real
files in a real repository based on a model's own proposed changes.
coding_agent/test_loop.py's coding_agent_loop() refuses to run against
this orchestrator project's own repo root unless allow_self_repo=True is
passed explicitly -- never point this at
/Users/andyyaro/Downloads/local-ai-orchestrator by default. Every write
goes through coding_agent/patch_tool.py's boundary-checked,
blocked-pattern-scanned propose_change()/apply_change(), and this
subsystem never calls git commit, git push, or any tagging command.
"""
