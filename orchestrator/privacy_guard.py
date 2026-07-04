"""
orchestrator/privacy_guard.py

Fail-closed secret scanning and minimal-payload construction for the
optional cloud fallback (Phase 7). Nothing built here is sent anywhere by
itself -- orchestrator/cloud_policy.py's should_attempt_cloud() and
request_human_approval() still gate every call -- but this module is what
makes sure a payload never contains more than a single role strictly
needs, and never a leaked secret.
"""

import re


class PrivacyGuardError(Exception):
    """Raised by guard_payload() when a likely secret is found in a
    built payload. The caller must not send the payload in this case."""


# Regex patterns for obvious secret-shaped strings: provider API key
# prefixes, AWS-style access key IDs, bearer tokens, and the `.env`-style
# `KEY_NAME=value` assignment shape for the provider key names this repo
# already documents (ANTHROPIC_API_KEY, OPENAI_API_KEY, AWS secret key).
_SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}"),                 # Anthropic-style
    re.compile(r"sk-[A-Za-z0-9]{20,}"),                        # OpenAI-style
    re.compile(r"AKIA[0-9A-Z]{16}"),                           # AWS access key ID
    re.compile(r"(?i)\baws_secret_access_key\s*=\s*\S+"),
    re.compile(r"(?i)\banthropic_api_key\s*=\s*\S+"),
    re.compile(r"(?i)\bopenai_api_key\s*=\s*\S+"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{20,}"),
    re.compile(r"(?i)\bapi[_-]?key\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}"),
]


def scan_for_secrets(text: str) -> list[str]:
    """
    Regex-scan `text` for obvious secret-shaped strings. Returns the list
    of matched substrings (empty if clean), so a caller or test can see
    exactly what tripped the check rather than just a boolean.
    """
    findings = []
    for pattern in _SECRET_PATTERNS:
        findings.extend(match.group(0) for match in pattern.finditer(text))
    return findings


def build_minimal_payload(
    role: str, goal: str, draft: str, extra: dict | None = None
) -> str:
    """
    Construct only what `role` specifically needs for a cloud escalation --
    never the full project state, other runs' history, other agents' raw
    intermediate output, file paths, or .env contents. `extra` is an
    explicit, opt-in dict of role-specific additions (e.g. the judge's
    scoring rubric text); any key not read by this function for the given
    role is deliberately dropped, not forwarded.

    - "judge": goal, the draft being scored, and extra["rubric"] (the
      scoring rubric text already used locally) -- nothing else.
    - "synthesizer": goal and the best draft only -- nothing else.
    - any other role: goal and draft only, as the most conservative
      default (no role-specific extras are ever included for an
      unrecognized role).
    """
    extra = extra or {}
    if role == "judge":
        rubric = extra.get("rubric", "")
        return (
            f"GOAL:\n{goal}\n\n"
            f"DRAFT TO SCORE:\n{draft}\n\n"
            f"SCORING RUBRIC:\n{rubric}"
        ).strip()
    if role == "synthesizer":
        return f"GOAL:\n{goal}\n\nBEST DRAFT:\n{draft}".strip()
    return f"GOAL:\n{goal}\n\nDRAFT:\n{draft}".strip()


def guard_payload(role: str, payload: str) -> str:
    """
    Scan `payload` for secrets and raise PrivacyGuardError if anything is
    found, rather than silently redacting and sending a possibly-still-
    sensitive payload. Fail closed: the payload is returned unchanged only
    when scan_for_secrets() finds nothing.
    """
    findings = scan_for_secrets(payload)
    if findings:
        raise PrivacyGuardError(
            f"Refusing to send cloud payload for role '{role}': "
            f"{len(findings)} likely secret(s) detected: {findings}"
        )
    return payload
