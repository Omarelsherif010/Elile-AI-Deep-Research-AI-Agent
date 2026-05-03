from __future__ import annotations

import html
import re

from research_agent.errors import GuardrailViolation
from research_agent.schemas import Claim

# ---------------------------------------------------------------------------
# Sensitive attribute patterns — used to block inference of protected classes.
# ---------------------------------------------------------------------------

SENSITIVE_ATTRIBUTE_PATTERNS: list[str] = [
    # health / medical
    r"\b(diagnosis|disease|disorder|HIV|cancer|diabetes|mental health|therapy|medication)\b",
    # religion
    r"\b(Muslim|Christian|Jewish|Hindu|Buddhist|religion|faith|church|mosque|temple)\b",
    # sexual orientation
    r"\b(gay|lesbian|bisexual|transgender|LGBTQ|queer|sexual orientation)\b",
    # race/ethnicity (as attribute inference — not neutral biographical fact)
]

# ---------------------------------------------------------------------------
# PII patterns — used to scrub or block claims containing personal identifiers.
# ---------------------------------------------------------------------------

PII_PATTERNS: list[str] = [
    r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
    r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b",  # phone number
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # email address
    r"\b\d{1,5}\s+\w+\s+(Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln)\b",  # street address
]

_COMPILED_PII = [re.compile(p, re.IGNORECASE) for p in PII_PATTERNS]
_COMPILED_SENSITIVE = [re.compile(p, re.IGNORECASE) for p in SENSITIVE_ATTRIBUTE_PATTERNS]

# Maximum allowed target name length (mirrors TargetProfile validation).
_MAX_NAME_LEN = 200


class Guardrails:
    """Layer of input/output safety checks enforcing the agent constitution."""

    def validate_input(self, target_name: str, **kwargs: object) -> None:
        """Validate target input.

        Raises GuardrailViolation if the target name is empty or exceeds 200 chars.
        """
        if not target_name or not target_name.strip():
            raise GuardrailViolation(
                rule="empty_target_name",
                detail="Target name must not be empty.",
            )
        if len(target_name) > _MAX_NAME_LEN:
            raise GuardrailViolation(
                rule="target_name_too_long",
                detail=f"Target name exceeds {_MAX_NAME_LEN} characters (got {len(target_name)}).",
            )

    def wrap_untrusted_content(self, url: str, content: str) -> str:
        """Wrap fetched web content in XML delimiters to defend against prompt injection.

        The content is HTML-escaped before wrapping so that any embedded XML/HTML
        characters in the raw page cannot escape the wrapper tags.
        """
        escaped_content = html.escape(content)
        return f'<source url="{url}">{escaped_content}</source>'

    def filter_pii(self, claim: Claim) -> Claim | None:
        """Return None if the claim contains PII or sensitive attributes; otherwise return claim.

        All textual fields of the claim (subject, predicate, object, attributes) are
        scanned against PII and sensitive attribute pattern lists.
        """
        text_to_check = _claim_text(claim)

        for pattern in _COMPILED_PII:
            if pattern.search(text_to_check):
                return None

        for pattern in _COMPILED_SENSITIVE:
            if pattern.search(text_to_check):
                return None

        return claim

    def check_output_safety(self, text: str) -> str:
        """Final scan of report text.

        Raises GuardrailViolation if:
        - PII patterns are detected in the output.
        - The report is missing a 'scope and limitations' section.

        Returns the text unchanged when it passes.
        """
        for pattern in _COMPILED_PII:
            if pattern.search(text):
                raise GuardrailViolation(
                    rule="pii_in_output",
                    detail="PII pattern detected in report output.",
                )

        if "scope and limitations" not in text.lower():
            raise GuardrailViolation(
                rule="missing_scope_section",
                detail="Report must contain a 'scope and limitations' section.",
            )

        return text


def _claim_text(claim: Claim) -> str:
    """Concatenate all textual fields of a claim into a single string for pattern matching."""
    parts = [claim.subject, claim.predicate, claim.object]
    parts.extend(claim.attributes.keys())
    parts.extend(claim.attributes.values())
    return " ".join(parts)
