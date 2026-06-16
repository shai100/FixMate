"""Fabrication detection — the safety gate that catches invented numbers.

An LLM might confidently state "torque to 45 Nm" even when no source says so, and
a wrong torque/pressure/voltage value can hurt a technician or wreck equipment.
This module scans a finished answer for numeric claims and part numbers and
verifies each one actually appears (verbatim, ignoring spacing) in the retrieved
source text. Any claim that isn't found is a "violation" and the composer treats
the answer as ungrounded (CLAUDE.md §8.1). It is deliberately backend-agnostic —
the same check runs whether the answer came from the local or cloud model.
"""

import re

# Numeric safety claims: torque, pressure, electrical, temperature, dimensions,
# speed. A wrong value here can harm a technician or damage equipment (CLAUDE.md
# §8.1 fabrication detection), so every match must be traceable to a chunk.
NUMERIC_CLAIM = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:n·?m|nm|bar|psi|kpa|mpa|kv|mv|v|volts?|ma|a|amps?|"
    r"ohms?|°\s?[cf]|mm|cm|rpm|hz)\b",
    re.IGNORECASE,
)
PART_NUMBER = re.compile(r"\b[A-Z]{2,}-?\d{2,}[A-Z0-9-]*\b")


def _normalize(s: str) -> str:
    """Collapse a claim to a spacing/case-insensitive token for comparison."""
    # Strip ALL whitespace and the middle dot so spacing variants of the same
    # claim ("12 Nm" / "12Nm" / "N·m") collapse to one comparable token before
    # substring containment against the retrieved corpus.
    return re.sub(r"\s+", "", s.lower().replace("·", ""))


def check_groundedness(answer: str, chunk_texts: list[str]) -> tuple[bool, list[str]]:
    """Post-process gate: every numeric/part claim in the answer must appear
    verbatim in the retrieved chunks. Returns (is_grounded, [violations]).

    This is the FR-4 / spec §8.4 safety check — backend-independent and run on
    every composed answer before it reaches a user.
    """
    corpus = _normalize(" ".join(chunk_texts))
    violations = [
        m.group(0)
        for rx in (NUMERIC_CLAIM, PART_NUMBER)
        for m in rx.finditer(answer)
        if _normalize(m.group(0)) not in corpus
    ]
    return (not violations, violations)
