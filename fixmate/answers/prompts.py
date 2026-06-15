from fixmate.retrieval.service import ScoredChunk

# Structured abstention: the model emits this sentinel (and nothing else) when the
# SOURCES don't support a safe answer. The composer detects it and routes to the
# FR-4 escalation path. This is the reliable out-of-corpus signal — retrieval
# scores cannot be trusted to separate relevant from irrelevant on small corpora
# (the MVP cosine reranker compresses scores), and a model asked to "just answer"
# will rationalize irrelevant chunks. Giving it a clean way to decline is safer.
ABSTAIN_SENTINEL = "INSUFFICIENT_CONTEXT"

SYSTEM_PROMPT = f"""You are FixMate, a troubleshooting assistant for field technicians.

Answer ONLY using the numbered SOURCES provided in the user message. Never use \
outside knowledge. Never invent part numbers, torque specs, pressures, electrical \
values, or procedures — if a value is not in the SOURCES, do not state it.

Decide first whether the SOURCES are relevant: do ANY of them mention the equipment, \
component, error code, or symptom named in the question? If YES, you MUST answer using \
those SOURCES. If NONE of the SOURCES mention the subject of the question at all (for \
example, the question asks about a component the SOURCES never reference), do NOT \
attempt an answer and do NOT cite anything — reply with exactly this single token and \
nothing else: {ABSTAIN_SENTINEL}

Write the answer in English with this structure:
1. SAFETY WARNINGS first — any lockout/tagout, depressurization, electrical, \
chemical, or pressure hazards mentioned in the sources.
2. A one-line diagnosis of the likely cause.
3. Numbered repair steps, each with the exact values and part numbers from the sources.
4. Required parts, if any are named in the sources.

Cite every factual claim with a marker `[chunk:<id>]` placed immediately after the \
claim, using the exact id shown for that source. Do not cite ids that are not in the \
SOURCES.

When a source is a FIELD FIX, it has been verified by a human curator. Present it \
prominently and prefix that guidance with its verification badge exactly as given in \
the source header.

If the sources do not contain enough information to answer safely, say so plainly and \
recommend escalation to a senior technician rather than guessing."""


def _badge(approver: str | None, approved_on: str | None) -> str:
    who = approver or "a curator"
    when = approved_on or "an earlier date"
    return f"Field-verified — approved by {who} on {when}"


def render_sources(
    chunks: list[ScoredChunk],
    fix_badges: dict[str, tuple[str | None, str | None]] | None = None,
) -> str:
    """Format retrieved chunks as the SOURCES block the model must ground in.

    `fix_badges` maps a fix_id (str) → (approver, approved_on) so field-fix
    sources carry the verification badge text the prompt instructs the model to
    surface (spec §2.4 approved-fix moat).
    """
    fix_badges = fix_badges or {}
    lines = []
    for c in chunks:
        header = f"[chunk:{c.chunk_id}]"
        if c.page is not None:
            header += f" (page {c.page})"
        if c.source_type == "field_fix":
            approver, approved_on = fix_badges.get(str(c.fix_id), (None, None))
            header += f" FIELD FIX — {_badge(approver, approved_on)}"
        else:
            header += " manual"
        lines.append(f"{header}\n{c.text}")
    return "\n\n".join(lines)


def build_user_prompt(
    question: str,
    chunks: list[ScoredChunk],
    fix_badges: dict[str, tuple[str | None, str | None]] | None = None,
) -> str:
    return (
        f"SOURCES:\n{render_sources(chunks, fix_badges)}\n\n"
        f"QUESTION: {question}\n\n"
        "Answer using only the SOURCES above, with inline [chunk:<id>] citations."
    )


def groundedness_retry_suffix(violations: list[str]) -> str:
    joined = ", ".join(violations)
    return (
        f"\n\nYour previous answer included values not found in the SOURCES: {joined}. "
        "Remove or correct every value that is not present verbatim in the SOURCES, "
        "then answer again."
    )


def escalation_answer(chunks: list[ScoredChunk]) -> str:
    """FR-4 low-confidence response: no fabricated body, point at the nearest
    sections, and offer human escalation."""
    if chunks:
        nearest = "\n".join(
            f"- {('page ' + str(c.page)) if c.page is not None else c.source_type}: "
            f"{' '.join(c.text.split())[:100]}"
            for c in chunks[:3]
        )
        nearest_block = f"\n\nThe closest information I found:\n{nearest}"
    else:
        nearest_block = ""
    return (
        "I don't have a confident, grounded answer for this in the available "
        "documentation, and I won't guess on something that could affect safety."
        f"{nearest_block}\n\n"
        "Please escalate to a senior technician or your administrator for verification."
    )
