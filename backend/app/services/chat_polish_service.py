"""Groq-powered polish — preserve structured markdown chat format."""

from __future__ import annotations

from app.services.llm_service import llm_service
from app.services.meta_chat import looks_like_maintenance_spam


async def polish_maintenance_reply(
    *,
    user_query: str,
    technical_brief: str,
    equipment_code: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> tuple[str, str]:
    """Return (polished_markdown, provider). Falls back to technical_brief if LLM unavailable."""
    brief = (technical_brief or "").strip()
    if not brief:
        return brief, "rule_based"

    # The agent formatter already produces the exact required structure (## sections +
    # ## Follow-up Questions). Preserve it verbatim so numbers/pricing are never lost or
    # reworded by the LLM. Polish is only used for unstructured briefs.
    if "## Follow-up Questions" in brief:
        return brief, "agents+ml"

    if not (llm_service.settings.groq_api_key or llm_service.settings.gemini_api_key):
        return brief, "agents+ml"

    asset = equipment_code or "the plant"
    system = (
        "You are ForgeMind — a Tata Steel reliability engineer.\n"
        "Rewrite the agent analysis into markdown using EXACTLY these sections:\n\n"
        "## Summary\n(2-4 sentences)\n\n"
        "## Key metrics\n"
        "- **Failure probability:** X%\n"
        "- **Remaining useful life:** ~X hours\n"
        "- **Risk level:** LOW/MEDIUM/HIGH/CRITICAL\n\n"
        "## Key findings\n- Cause (XX% confidence)\n\n"
        "## Recommended actions\n1. Action (timeframe: ASAP / next shift / planned outage)\n\n"
        "## Follow-up Questions\n-> Question one\n-> Question two\n-> Question three\n\n"
        "Rules: no emoji, no invented numbers, keep sections short, professional tone.\n"
        f"Asset: {asset}"
    )
    prompt = (
        f"User question:\n{user_query}\n\n"
        f"Agent analysis (source of truth):\n{brief[:4000]}"
    )
    try:
        text = await llm_service.generate(prompt, system=system, history=history)
        polished = (text or "").strip()
        if polished and "## Summary" in polished and not looks_like_maintenance_spam(polished):
            return polished, llm_service.last_provider
    except Exception:
        pass

    return brief, "agents+ml"
