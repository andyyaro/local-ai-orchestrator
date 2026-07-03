"""Command-line entry point for the Local AI Orchestrator.

This milestone connects the terminal command to one local Ollama model call. Later
milestones will route the same goal through the full multi-agent pipeline.
"""

from __future__ import annotations

import argparse
import sys

from core.config import ConfigError, get_active_profile, get_model_for_role, load_model_config
from core.ollama_client import OllamaClient, OllamaError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Local AI Orchestrator MVP.")
    parser.add_argument("--goal", required=False, default="Explain recursion.", help="User goal to send through the orchestrator.")
    parser.add_argument("--mode", required=False, default="planning", help="Workflow mode, such as writing, coding, planning, debugging, or study.")
    parser.add_argument("--profile", required=False, default=None, help="Override the active model profile from config/models.yaml.")
    parser.add_argument("--role", required=False, default="supervisor", help="Agent role model to use for this first local call.")
    parser.add_argument("--max-loops", type=int, default=1, help="Maximum improvement loops to run later in the full MVP.")
    parser.add_argument("--threshold", type=int, default=40, help="Judge score threshold for passing later in the full MVP.")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Local Ollama server URL.")
    return parser.parse_args()


def resolve_profile(profile_override: str | None) -> tuple[str, dict[str, object]]:
    """Load the configured model profile, with an optional CLI override."""
    model_config = load_model_config()

    if profile_override:
        profiles = model_config.get("profiles", {})
        if not isinstance(profiles, dict) or profile_override not in profiles:
            raise ConfigError(f"Profile '{profile_override}' is not defined in config/models.yaml.")
        profile = profiles[profile_override]
        if not isinstance(profile, dict):
            raise ConfigError(f"Profile '{profile_override}' must be a YAML mapping.")
        return profile_override, profile

    return get_active_profile(model_config)


def build_first_prompt(goal: str, mode: str, role: str) -> str:
    """Build the first prompt sent to Ollama."""
    return f"""You are the {role} agent in a local multi-agent AI orchestrator.

Current milestone: first successful local Ollama model call.

User goal:
{goal}

Workflow mode: {mode}

Respond with:
1. A cleaned-up version of the user's goal.
2. The likely workflow mode.
3. Three short next steps for the orchestrator.
Keep the response concise and practical.
"""


def main() -> int:
    args = parse_args()

    try:
        profile_name, profile = resolve_profile(args.profile)
        model = get_model_for_role(args.role, profile)
        keep_alive = str(profile.get("keep_alive", "5m"))
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    client = OllamaClient(base_url=args.ollama_url)

    if not client.health_check():
        print("Ollama is not reachable.", file=sys.stderr)
        print("Start the Ollama app or run `ollama serve`, then verify with:", file=sys.stderr)
        print("curl http://localhost:11434", file=sys.stderr)
        return 1

    prompt = build_first_prompt(args.goal, args.mode, args.role)

    print("Local AI Orchestrator — first Ollama call")
    print(f"Profile: {profile_name}")
    print(f"Role: {args.role}")
    print(f"Model: {model}")
    print(f"Keep alive: {keep_alive}")
    print("\n--- Model response ---\n")

    try:
        response = client.generate(
            model=model,
            prompt=prompt,
            keep_alive=keep_alive,
            options={"temperature": 0.2, "num_ctx": 2048},
        )
    except OllamaError as exc:
        print(f"Ollama error: {exc}", file=sys.stderr)
        return 1

    print(response)
    print("\n--- Done ---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
