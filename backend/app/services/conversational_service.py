"""Natural conversational + navigation responses (Groq-powered when available)."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from app.services.agents.intent_classifier import (
    _is_greeting,
    _matches_any,
    is_definition_query,
    normalize_message,
)
from app.services.llm_service import llm_service
from app.services.meta_chat import identity_reply, is_meta_conversational, looks_like_maintenance_spam
from app.services.portal_navigation import (
    format_greeting_markdown,
    format_navigation_markdown,
    is_navigation_query,
    resolve_navigation,
)


async def conversational_reply(
    message: str,
    *,
    equipment_code: str | None = None,
    equipment_name: str = "",
    history: list[dict[str, str]] | None = None,
) -> tuple[str, str]:
    """Return (markdown_text, llm_provider_used)."""
    m = normalize_message(message).lower()

    # Definition / glossary ("full form of SOP") must beat navigation ("go to documents")
    glossary = _glossary_answer(message)
    if glossary:
        return glossary, "copilot"

    if is_navigation_query(message):
        link = resolve_navigation(message)
        if link:
            return format_navigation_markdown(link, equipment_code=equipment_code), "navigation"

    if _is_greeting(m):
        return format_greeting_markdown(equipment_code=equipment_code, equipment_name=equipment_name), "greeting"

    static = _static_conversational_answer(message, equipment_code=equipment_code)
    if static:
        return static, "copilot"

    if is_meta_conversational(message):
        return identity_reply(), "copilot"

    if llm_service.settings.groq_api_key or llm_service.settings.gemini_api_key:
        try:
            text = await llm_service.generate(
                message,
                system=_conversational_system_prompt(equipment_code, equipment_name),
                history=history,
                chat_mode=True,
            )
            cleaned = (text or "").strip()
            # Only use the LLM output if a real provider answered (not the rule-based fallback)
            if (
                cleaned
                and len(cleaned) > 3
                and llm_service.last_provider not in ("rule_based", "unknown")
                and not looks_like_maintenance_spam(cleaned)
            ):
                return _ensure_markdown_links(cleaned), llm_service.last_provider
        except Exception:
            pass

    return _friendly_offline_reply(equipment_code), "copilot"


def _friendly_offline_reply(equipment_code: str | None) -> str:
    if equipment_code:
        return (
            f"I'm **ForgeMind**. I can help with **{equipment_code}** using live sensors, "
            f"ML predictions, and agentic reasoning — try *\"what should we do?\"* or *\"what's the RUL?\"*"
        )
    return (
        "I'm **ForgeMind**, your agentic plant copilot. I handle navigation, fleet ranking, and asset diagnostics. "
        "Switch to **Asset mode** for a specific unit, or ask *\"rank all assets by RUL\"*."
    )


def _conversational_system_prompt(equipment_code: str | None, equipment_name: str) -> str:
    if equipment_code:
        asset = f"{equipment_code} ({equipment_name})" if equipment_name else equipment_code
    else:
        asset = "General plant-wide chat (no single asset selected)"
    return (
        "You are ForgeMind — a friendly agentic AI copilot for Tata Steel maintenance engineers.\n"
        "This is CASUAL CHAT. Answer naturally and warmly like ChatGPT.\n"
        "Rules:\n"
        "- For name/identity: say you are ForgeMind, an agentic AI plant copilot for Tata Steel\n"
        "- Keep replies SHORT (1-3 sentences) for greetings and meta questions\n"
        "- Be helpful and proactive: if useful, suggest one relevant next step\n"
        "- NEVER output sensor readings, RUL, root cause, or maintenance actions unless explicitly asked\n"
        "- NEVER use headers like 'Maintenance Assessment' or 'Immediate actions'\n"
        "- NEVER mention internal architecture like 'Supervisor', 'agents', or model providers\n"
        "- For navigation, use markdown links like [Live Monitor](/monitor)\n"
        f"- Asset context: {asset}\n"
    )


_GLOSSARY: dict[str, tuple[str, str, str]] = {
    "rul": ("RUL", "Remaining Useful Life", "the estimated time (in hours or cycles) an asset can keep operating before it likely needs maintenance or fails."),
    "sop": ("SOP", "Standard Operating Procedure", "the documented step-by-step instructions for safely operating or servicing equipment."),
    "rca": ("RCA", "Root Cause Analysis", "the method of finding the underlying cause of a fault rather than just treating the symptom."),
    "c-mapss": ("C-MAPSS", "Commercial Modular Aero-Propulsion System Simulation", "NASA's turbofan degradation dataset used to train the predictive RUL models here."),
    "cmapss": ("C-MAPSS", "Commercial Modular Aero-Propulsion System Simulation", "NASA's turbofan degradation dataset used to train the predictive RUL models here."),
    "ml": ("ML", "Machine Learning", "the models that predict failure probability and RUL from live sensor data."),
    "kpi": ("KPI", "Key Performance Indicator", "a metric used to track maintenance and reliability performance."),
    "pm": ("PM", "Preventive Maintenance", "scheduled maintenance done before failure to keep assets healthy."),
    "mtbf": ("MTBF", "Mean Time Between Failures", "the average operating time between one failure and the next."),
    "fmea": ("FMEA", "Failure Mode and Effects Analysis", "a structured method to identify how a component can fail and the impact of each failure."),
    "ai": ("AI", "Artificial Intelligence", "here, the agentic reasoning that combines sensors, ML, and plant knowledge to answer your questions."),
}


def _glossary_answer(message: str) -> str | None:
    if not is_definition_query(message):
        return None
    m = normalize_message(message).lower()
    for key, (abbr, full, desc) in _GLOSSARY.items():
        if re.search(rf"\b{re.escape(key)}\b", m):
            return f"**{abbr}** stands for **{full}** — {desc}"
    return None


def _static_conversational_answer(message: str, *, equipment_code: str | None) -> str | None:
    m = normalize_message(message).lower()
    now = datetime.now(timezone.utc)

    glossary = _glossary_answer(message)
    if glossary:
        return glossary

    if _matches_any(m, (r"\btoday'?s date\b", r"\bwhat(?:'s| is) (?:the )?date\b", r"\bcurrent date\b", r"\bwhat day is")):
        return f"Today is **{now.strftime('%A, %B %d, %Y')}**."

    if re.search(r"\bwhat time is it\b", m):
        return f"It's **{now.strftime('%H:%M')} UTC** right now."

    if _matches_any(m, (
        r"\bwho are you\b", r"\bwhat are you\b", r"\byour name\b",
        r"\bwhat(?:'s| is) your name\b", r"\bwho made you\b", r"\bwho created you\b",
    )):
        return identity_reply()

    if _matches_any(m, (r"\bthank", r"\bthanks\b")):
        return "You're welcome. Ask anytime if you need help on the plant floor."

    if _matches_any(m, (r"\bhow are you\b", r"\bhow r u\b")):
        return "Doing great and ready to help! What do you need on the plant floor today?"

    if _matches_any(m, (r"\bwhat can you do\b", r"\bhow do you work\b")):
        return (
            "I'm an **agentic AI** — I reason across live sensors, ML predictions, and plant knowledge to diagnose assets, "
            "rank the fleet by risk, plan maintenance, and answer questions. "
            "For diagnostics, switch to **Asset mode** and ask *\"what should we do?\"*"
        )

    if _matches_any(m, (r"\bhelp me\b", r"\bhelp\b")) and len(m.split()) <= 3:
        return "Sure — ask about navigation, fleet health, or pick an asset for diagnostics. What do you need?"

    return None


def _ensure_markdown_links(text: str) -> str:
    replacements = [
        ("Live Monitor", "[Live Monitor](/monitor)"),
        ("Dashboard", "[Dashboard](/dashboard)"),
        ("Priority Queue", "[Priority Queue](/priority)"),
        ("Decision Simulator", "[Decision Simulator](/simulate)"),
        ("Logbook", "[Logbook](/logbook)"),
        ("Alerts", "[Alerts](/alerts)"),
    ]
    for label, link in replacements:
        if label in text and f"[{label}]" not in text:
            text = text.replace(label, link, 1)
    return text
