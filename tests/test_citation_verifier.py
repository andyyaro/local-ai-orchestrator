"""
tests/test_citation_verifier.py

Phase 10: deterministic citation verification. No test here makes a real
network call -- SourceRegistry is populated directly with hand-constructed
source text, never fetched for real.
"""

from research.citation_verifier import (
    detect_contradictions,
    extract_claims,
    reject_unverified_citations,
    verify_citation,
)
from research.source_registry import SourceRegistry


def _registry_with(sources: dict[str, str]) -> SourceRegistry:
    """Build a SourceRegistry with source_id -> text mappings, e.g.
    {"S1": "..."} -- registered in order so S1 gets id S1, etc."""
    registry = SourceRegistry()
    for source_id, text in sources.items():
        registry.register(
            url=f"https://example.com/{source_id}",
            title=source_id,
            fetched_at="2026-07-04T00:00:00",
            content_hash="deadbeef",
            text=text,
        )
    return registry


# ── extract_claims ─────────────────────────────────────────────────────────────

def test_extract_claims_parses_multi_citation_report_into_distinct_claims():
    report = (
        "Sleep improves memory consolidation.[1] "
        "Regular exercise reduces cardiovascular risk.[2] "
        "This sentence has no citation at all. "
        "Connection pooling reduces database latency under load.[1][3]"
    )

    claims = extract_claims(report)

    assert len(claims) == 3
    assert claims[0].citation_markers == [1]
    assert "memory consolidation" in claims[0].text
    assert claims[1].citation_markers == [2]
    assert "cardiovascular" in claims[1].text
    assert claims[2].citation_markers == [1, 3]
    assert "Connection pooling" in claims[2].text


# ── verify_citation ────────────────────────────────────────────────────────────

def test_verify_citation_true_for_claim_with_genuinely_supporting_source():
    registry = _registry_with({
        "S1": "Sleep plays a critical role in memory consolidation and "
              "cognitive function, according to numerous studies.",
    })
    claims = extract_claims("Sleep improves memory consolidation and cognitive function.[1]")

    assert verify_citation(claims[0], registry) is True


def test_verify_citation_false_for_nonexistent_source_id():
    """The direct fabricated-citation case: citing a source_id that was
    never registered at all."""
    registry = _registry_with({"S1": "Some unrelated source text."})
    claims = extract_claims("This claim cites a source that doesn't exist.[7]")

    assert verify_citation(claims[0], registry) is False


def test_verify_citation_false_when_source_exists_but_does_not_support_claim():
    registry = _registry_with({
        "S1": "The history of tea cultivation spans thousands of years "
              "across many different cultures and continents.",
    })
    claims = extract_claims(
        "Quantum computers use superconducting qubits to perform calculations.[1]"
    )

    assert verify_citation(claims[0], registry) is False


# ── reject_unverified_citations ─────────────────────────────────────────────────

def test_reject_unverified_citations_flags_exactly_the_unverified_claims():
    registry = _registry_with({
        "S1": "Sleep plays a critical role in memory consolidation and "
              "cognitive function, according to numerous studies.",
        "S2": "The history of tea cultivation spans thousands of years.",
    })
    report = (
        "Sleep improves memory consolidation and cognitive function.[1] "
        "Quantum computers use superconducting qubits.[2] "
        "This unrelated fabricated claim cites nothing real.[9]"
    )

    annotated, failed = reject_unverified_citations(report, registry)

    assert "[UNVERIFIED CITATION] Sleep improves memory consolidation" not in annotated
    assert "Sleep improves memory consolidation" in annotated
    assert "[UNVERIFIED CITATION] Quantum computers" in annotated
    assert "[UNVERIFIED CITATION] This unrelated fabricated claim" in annotated
    assert len(failed) == 2
    assert any("Quantum computers" in claim for claim in failed)
    assert any("fabricated claim" in claim for claim in failed)


# ── detect_contradictions ────────────────────────────────────────────────────
#
# NOTE: this is a documented heuristic, not a fact-checker. It catches an
# obvious, surface-level contradiction (shared topic words + a negation
# word on only one side) but will miss contradictions phrased with
# different vocabulary or without an explicit negation word -- see the
# function's own docstring for the same caveat.

def test_detect_contradictions_catches_an_obvious_constructed_contradiction():
    claims = extract_claims(
        "Regular exercise reduces cardiovascular disease risk significantly.[1] "
        "Regular exercise does not reduce cardiovascular disease risk at all.[2]"
    )

    contradictions = detect_contradictions(claims)

    assert len(contradictions) == 1
    claim_a, claim_b = contradictions[0]
    assert "does not" in claim_b.text or "does not" in claim_a.text


def test_detect_contradictions_finds_nothing_for_unrelated_claims():
    claims = extract_claims(
        "Sleep improves memory consolidation.[1] "
        "Connection pooling reduces database latency.[2]"
    )

    assert detect_contradictions(claims) == []
