"""Last check before a reply leaves the system.

A reply may not claim an action that was never performed ("I've passed this to the team" when no escalation was
recorded) - the situation that made customers believe a person was involved when none was.
"""
import re

CLAIMS_ACTION = re.compile(
    r"(?:\bi(?:'ve| have)|\bwe(?:'ve| have)) (?:just )?(?:passed|forwarded|escalated|flagged|asked|contacted|informed|"
    r"notified|raised|shared|handed)\b[^.!?\n]*[.!?]?|"
    r"\b(?:connecting|connected|transferring|transferred) you (?:with|to)\b[^.!?\n]*[.!?]?|"
    r"\b(?:my )?(?:teammate|colleague|the team|our team|a teammate|support team) (?:is|has|will|are)(?: already)? "
    r"(?:looking|reviewing|reach|reply|get back|contact|call|take)\b[^.!?\n]*[.!?]?",
    re.I,
)


def claims_unperformed_action(text: str) -> bool:
    return bool(CLAIMS_ACTION.search(text or ""))


def enforce_outbound(text: str, *, escalated: bool) -> tuple[str, list[str]]:
    """Return (possibly corrected text, issues found). Escalation language is only allowed after a real handoff."""
    issues: list[str] = []
    if not escalated and claims_unperformed_action(text):
        cleaned = CLAIMS_ACTION.sub("", text)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        issues.append("claimed an action that was not performed")
        if len(cleaned) >= 20:
            return cleaned, issues
    return text, issues
