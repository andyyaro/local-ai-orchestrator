"""
research/run_research.py

Narrow, separate deep-research pipeline entry point (Phase 10) -- kept
out of the existing 7-agent loop in run.py, since a research task
(search -> fetch -> draft-with-citations -> verify) has a fundamentally
different shape than a writing or coding task.

Requires BOTH research.internet_enabled: true in config/models.yaml AND
the --enable-research CLI flag, mirroring Phase 7's double-gate pattern
for cloud escalation. Missing either one refuses to run rather than
silently falling back to something else -- unlike cloud escalation, there
is no local-only equivalent of a research task to fall back to.

Run with:
    python -m research.run_research --goal "..." --enable-research
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from agents.builder import BuilderAgent
from agents.synthesizer import SynthesizerAgent
from orchestrator.config_loader import get_model_for_role, get_research_config
from research.citation_verifier import reject_unverified_citations
from research.fetcher import FetchError, RobotsDisallowedError, fetch_url
from research.prompt_injection_guard import sanitize_fetched_content, wrap_untrusted_content
from research.search_provider import get_search_provider
from research.source_registry import SourceRegistry, hash_content


def run_research(
    goal: str, run_dir: Path, internet_enabled: bool, enable_research_flag: bool,
) -> dict:
    """
    Run the narrow research pipeline: search, fetch + sanitize each
    result, draft a cited report with the existing Builder/Synthesizer
    agents, then reject any citation that doesn't verify against the
    fetched sources.

    Raises RuntimeError immediately if either gate condition is missing
    -- see module docstring for why both are required.
    """
    if not (internet_enabled and enable_research_flag):
        raise RuntimeError(
            "Deep research requires BOTH research.internet_enabled: true in "
            "config/models.yaml AND the --enable-research CLI flag. Got "
            f"internet_enabled={internet_enabled}, "
            f"--enable-research={enable_research_flag}."
        )

    config = get_research_config()
    provider = get_search_provider(config.get("search_provider", "mock"))
    max_sources = config.get("max_sources", 8)

    registry = SourceRegistry()
    context_blocks = []

    for result in provider.search(goal, max_sources):
        try:
            page = fetch_url(result.url)
        except (RobotsDisallowedError, FetchError) as exc:
            print(f"  [Research] Skipping {result.url}: {exc}")
            continue

        sanitized_text = sanitize_fetched_content(page.text)
        source_id = registry.register(
            url=page.url,
            title=result.title,
            fetched_at=page.fetched_at,
            content_hash=hash_content(sanitized_text),
            text=sanitized_text,
        )
        context_blocks.append(
            wrap_untrusted_content(
                f"{source_id}: {result.title} ({page.url})", sanitized_text,
            )
        )

    sources_context = "\n\n".join(context_blocks)
    research_goal = (
        f"{goal}\n\n"
        "Write a cited research report. Cite sources using footnote "
        "markers like [1], [2] matching the source numbers below "
        "(S1 -> [1], S2 -> [2], etc.). Only cite a source for a claim it "
        "actually supports.\n\n"
        f"{sources_context}"
    )

    builder = BuilderAgent(model=get_model_for_role("builder", "general"))
    draft = builder.run(goal=research_goal, plan=goal, mode="general")

    synthesizer = SynthesizerAgent(model=get_model_for_role("synthesizer", "general"))
    final_report = synthesizer.run(goal=goal, best_draft=draft, score=0, iterations=1)

    verified_report, failed_claims = reject_unverified_citations(final_report, registry)

    run_dir.mkdir(parents=True, exist_ok=True)
    registry.save(run_dir / "source_registry.json")
    (run_dir / "research_report.txt").write_text(verified_report, encoding="utf-8")
    (run_dir / "verification_results.json").write_text(
        json.dumps({"failed_claims": failed_claims}, indent=2), encoding="utf-8",
    )

    return {
        "report": verified_report,
        "failed_claims": failed_claims,
        "sources": registry.all_sources(),
        "run_dir": str(run_dir),
    }


def main():
    parser = argparse.ArgumentParser(description="Deep research pipeline (Phase 10)")
    parser.add_argument("--goal", required=True, help="The research question or topic.")
    parser.add_argument(
        "--enable-research", action="store_true", default=False,
        help="Required, in addition to research.internet_enabled: true in "
             "config/models.yaml, before any real search/fetch happens.",
    )
    args = parser.parse_args()

    config = get_research_config()
    run_dir = Path("runs") / f"research_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    result = run_research(
        goal=args.goal,
        run_dir=run_dir,
        internet_enabled=config.get("internet_enabled", False),
        enable_research_flag=args.enable_research,
    )

    print(result["report"])
    if result["failed_claims"]:
        print(f"\n[WARNING] {len(result['failed_claims'])} unverified claim(s) flagged "
              "in the report above -- see verification_results.json.")
    print(f"\nRun saved to: {result['run_dir']}/")


if __name__ == "__main__":
    main()
