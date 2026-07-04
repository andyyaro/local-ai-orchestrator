"""
research/citation_verifier.py

Deterministic citation verification for Phase 10 deep research -- the
backstop for prompts/judge.txt's "fabricated_citations" hard-fail
category, which has never had a real enforcement mechanism, exactly like
the word-limit constraint before Phase 2's validators existed. An LLM
judge is no more reliable at verifying a citation than it was at counting
words.
"""

import re
from dataclasses import dataclass

from research.source_registry import SourceRegistry

_CITATION_MARKER = re.compile(r"\[(\d+)\]")

# A conservative baseline for "the source has reasonable overlap with the
# claim": share at least this fraction of the claim's significant words
# with the source text (naive lowercase word overlap, stopwords removed).
# This is a heuristic, not semantic understanding -- see verify_citation()'s
# docstring for what it deliberately does not guarantee.
_KEYWORD_OVERLAP_THRESHOLD = 0.4

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "of", "in", "on", "to",
    "and", "or", "for", "with", "that", "this", "it", "as", "by", "at",
    "from", "be", "has", "have", "had", "not", "but", "its", "will",
    "which", "their", "they", "there",
}

_NEGATION_WORDS = {
    "not", "no", "never", "isn't", "wasn't", "doesn't", "don't", "won't",
    "cannot", "can't", "aren't", "weren't", "didn't",
}


@dataclass
class Claim:
    """One sentence from a research report that cites at least one
    source, plus the numeric footnote markers it cites (e.g. [1] -> 1)."""
    text: str
    citation_markers: list[int]


_SENTENCE_BOUNDARY = re.compile(r"[.!?](?:\[\d+\])*(?=\s|$)")


def extract_claims(report_text: str) -> list[Claim]:
    """
    Parse footnote-style citation markers ([1], [2], ...) out of
    `report_text` and associate each with the sentence it appears in.
    Sentences with no citation marker are not returned as claims -- only
    cited assertions need verification.

    Sentence boundaries are detected at [.!?] optionally followed
    immediately by one or more citation markers (e.g. "claim.[1][2] Next
    sentence...") -- a plain split on punctuation-then-whitespace would
    miss every boundary here, since the marker sits between the
    punctuation and the following space.
    """
    claims: list[Claim] = []
    text = report_text.strip()
    start = 0
    for match in _SENTENCE_BOUNDARY.finditer(text):
        sentence = text[start:match.end()].strip()
        start = match.end()
        markers = [int(m) for m in _CITATION_MARKER.findall(sentence)]
        if markers:
            claims.append(Claim(text=sentence, citation_markers=markers))
    return claims


def _significant_words(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z']+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def verify_citation(claim: Claim, registry: SourceRegistry) -> bool:
    """
    Confirm every source a claim cites actually exists in `registry`
    (source_id `f"S{marker}"` for each numeric marker), and that each
    source's fetched text contains reasonable keyword support for the
    claim.

    This is a substring/keyword-overlap baseline, not semantic
    verification: a claim can share enough words with an unrelated
    passage to pass, or restate the same idea in different words and
    fail. Treat this as reliably catching fabricated or absent citations
    (the direct case prompts/judge.txt's fabricated_citations category
    names), and approximately catching unsupported-but-plausible-looking
    ones -- not as a complete fact-checker.
    """
    claim_words = _significant_words(claim.text)
    if not claim_words:
        return False

    for marker in claim.citation_markers:
        source = registry.get_source(f"S{marker}")
        if source is None:
            return False

        source_words = _significant_words(source.get("text", ""))
        if not source_words:
            return False

        overlap = claim_words & source_words
        if len(overlap) / len(claim_words) < _KEYWORD_OVERLAP_THRESHOLD:
            return False

    return True


def detect_contradictions(claims: list[Claim]) -> list[tuple[Claim, Claim]]:
    """
    Best-effort heuristic: flag pairs of claims that share significant
    topic overlap but assert opposite things (one has a negation word
    near otherwise-similar claim text, the other doesn't).

    This is NOT a guarantee and has real false-negative risk: many
    genuine contradictions won't share enough surface-level words, or
    won't use an explicit negation word, to be caught here. Read this as
    "catches some obvious, surface-level contradictions," never as
    "confirms the report is internally consistent."
    """
    contradictions = []

    for i, claim_a in enumerate(claims):
        words_a = _significant_words(claim_a.text)
        negated_a = bool(_NEGATION_WORDS & set(claim_a.text.lower().split()))
        for claim_b in claims[i + 1:]:
            words_b = _significant_words(claim_b.text)
            if not words_a or not words_b:
                continue
            overlap = words_a & words_b
            topic_overlap = len(overlap) / min(len(words_a), len(words_b))
            negated_b = bool(_NEGATION_WORDS & set(claim_b.text.lower().split()))
            if topic_overlap >= 0.5 and negated_a != negated_b:
                contradictions.append((claim_a, claim_b))

    return contradictions


def reject_unverified_citations(
    report_text: str, registry: SourceRegistry
) -> tuple[str, list[str]]:
    """
    The enforcement step: extract every cited claim, verify each against
    `registry`, and return the report with unverified claims clearly
    flagged (prefixed with "[UNVERIFIED CITATION]") plus a list of the
    specific claim texts that failed. A report with any unverified
    citation must never be presented as a finished, trustworthy result --
    mirroring exactly how Phase 2's validators and the existing
    code-verification hard-fail both already refuse to let a high score
    paper over a real problem. Verified claims are left untouched.
    """
    claims = extract_claims(report_text)
    failed: list[str] = []
    annotated_report = report_text

    for claim in claims:
        if not verify_citation(claim, registry):
            failed.append(claim.text)
            annotated_report = annotated_report.replace(
                claim.text, f"[UNVERIFIED CITATION] {claim.text}"
            )

    return annotated_report, failed
