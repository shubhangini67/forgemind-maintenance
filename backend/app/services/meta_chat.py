"""Detect meta / small-talk queries that must never hit the maintenance pipeline."""

from __future__ import annotations

import re

from app.services.agents.intent_classifier import normalize_message, _is_greeting, _matches_any

_META_PATTERNS = (
    r"\byour name\b",
    r"\bwhat(?:'s| is) your name\b",
    r"\bwhats your name\b",
    r"\bwho are you\b",
    r"\bwhat are you\b",
    r"\bwho made you\b",
    r"\bwho created you\b",
    r"\btell me about yourself\b",
    r"\bare you (?:an? )?(?:ai|bot|robot|real)\b",
    r"\bhow old are you\b",
    r"\bwhat model\b",
    r"\bwhich model\b",
    r"\bcan you help me\b",
    r"\bhello\b",
    r"\bhi\b",
    r"\bhey\b",
)

_MAINTENANCE_SPAM_MARKERS = (
    "Maintenance Assessment (C-MAPSS-calibrated)",
    "Live C-MAPSS-calibrated sensors",
    "Configure GEMINI_API_KEY or GROQ_API_KEY",
    "## Probable Root Causes",
)


def is_meta_conversational(message: str) -> bool:
    m = normalize_message(message).lower()
    if _is_greeting(m):
        return True
    if _matches_any(m, _META_PATTERNS):
        return True
    if len(m.split()) <= 4 and not any(
        w in m for w in (
            "rul", "fault", "bearing", "vibration", "spare", "degrad", "sensor", "maint",
            "fix", "urgent", "plan", "do", "act",
        )
    ):
        if _matches_any(m, (r"\bwho\b", r"\bhow are you\b", r"\bname\b", r"\bwhat(?:'s| is) your name\b")):
            return True
    return False


def looks_like_maintenance_spam(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    return any(marker in t for marker in _MAINTENANCE_SPAM_MARKERS)


def identity_reply() -> str:
    return (
        "I'm **ForgeMind** — an agentic AI copilot for Tata Steel maintenance. "
        "I reason across live sensors, ML predictions, and plant knowledge to answer your questions. "
        "Ask me anything about the plant, or switch to **Asset mode** for unit-specific diagnostics."
    )
