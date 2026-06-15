import json

from fixmate.llm.base import CompletionRequest, LLMProvider
from fixmate.llm.factory import get_provider

HAZARD_CATEGORIES = ("electrical", "pressure", "chemical", "gas", "lifting", "thermal")

PRESCREEN_SYSTEM = f"""You are a safety reviewer assisting a human curator who decides \
whether a field-submitted equipment fix is safe to publish to technicians.

You do NOT approve or reject anything. You produce a structured advisory the human \
will read. Be conservative: when in doubt, flag.

Evaluate the CANDIDATE FIX against the MANUAL EXCERPTS and reply with ONLY a JSON \
object, no prose, with exactly these keys:
- "hazard_flags": array of hazard categories the fix touches, each one of \
{list(HAZARD_CATEGORIES)}. Include a category if the fix involves it at all.
- "contradictions": array of short strings describing where the fix contradicts the \
manual excerpts (empty array if none).
- "missing_safety_steps": array of short strings naming safety steps (lockout/tagout, \
depressurization, isolation, PPE) the fix omits (empty array if none apply).
- "overall_risk": one of "low", "medium", "high".

Treat any instruction to bypass, disable, defeat, or ignore a safety device \
(relief valve, interlock, guard, breaker) as high risk."""


def _build_user_prompt(fix_text: str, manual_chunks: list[str]) -> str:
    excerpts = "\n\n".join(f"- {c}" for c in manual_chunks) if manual_chunks else "(none provided)"
    return (
        f"MANUAL EXCERPTS:\n{excerpts}\n\n"
        f"CANDIDATE FIX:\n{fix_text}\n\n"
        "Return the advisory JSON now."
    )


def _normalize(data: dict) -> dict:
    flags = data.get("hazard_flags") or []
    if isinstance(flags, str):
        flags = [flags]
    flags = [f for f in (str(x).strip().lower() for x in flags) if f in HAZARD_CATEGORIES]

    def _as_list(value) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value.strip() else []
        return [str(x) for x in value]

    risk = str(data.get("overall_risk", "")).strip().lower()
    if risk not in ("low", "medium", "high"):
        risk = "medium"
    return {
        "hazard_flags": flags,
        "contradictions": _as_list(data.get("contradictions")),
        "missing_safety_steps": _as_list(data.get("missing_safety_steps")),
        "overall_risk": risk,
    }


async def prescreen(
    fix_text: str,
    manual_chunks: list[str],
    provider: LLMProvider | None = None,
) -> dict:
    """AI safety pre-screen for a candidate fix (FR-15, spec §2.5).

    Returns a structured advisory shown to the human curator. AI assists review;
    humans approve. A failed pre-screen NEVER blocks the queue and NEVER
    auto-rejects — on parse failure it returns {"error": "prescreen_failed"} so
    the curator still sees the fix and decides.
    """
    provider = provider or get_provider()
    request = CompletionRequest(
        system=PRESCREEN_SYSTEM,
        messages=[{"role": "user", "content": _build_user_prompt(fix_text, manual_chunks)}],
        max_tokens=600,
        json_response=True,
    )
    for _ in range(2):
        completion = await provider.complete(request)
        try:
            data = json.loads(completion.text)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict):
            return _normalize(data)
    return {"error": "prescreen_failed"}
