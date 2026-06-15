"""Classify chat queries into maintenance intents before agent execution."""

from __future__ import annotations

import re
from datetime import datetime, timezone

# Canonical chat intents (supervisor routes on these)
DIAGNOSTIC = "diagnostic"
ROOT_CAUSE = "diagnostic"  # alias — same routing as diagnostic
RISK = "risk"
MAINTENANCE_PLANNING = "maintenance_planning"
INVENTORY = "inventory"
SOP = "sop"
FAILURE_SIMULATION = "failure_simulation"
ASSET_RANKING = "asset_ranking"
BUSINESS_IMPACT = "business_impact"
REPORT = "report"
CONVERSATIONAL = "conversational"

INTENT_LABELS: dict[str, str] = {
    DIAGNOSTIC: "Root Cause Analysis Query",
    RISK: "Risk Query",
    MAINTENANCE_PLANNING: "Maintenance Planning Query",
    INVENTORY: "Inventory Query",
    SOP: "SOP / Knowledge Query",
    FAILURE_SIMULATION: "Failure Simulation Query",
    ASSET_RANKING: "Asset Ranking Query",
    BUSINESS_IMPACT: "Business Impact Query",
    REPORT: "Report Query",
    CONVERSATIONAL: "General Conversational Query",
}

# Maps intent → UI / synthesis template id
RESPONSE_TEMPLATE_BY_INTENT: dict[str, str] = {
    ASSET_RANKING: "asset_ranking",
    BUSINESS_IMPACT: "business_impact",
    DIAGNOSTIC: "root_cause_analysis",
    MAINTENANCE_PLANNING: "maintenance_plan",
    SOP: "sop_knowledge",
    FAILURE_SIMULATION: "failure_simulation",
    INVENTORY: "critical_spares",
    RISK: "business_impact",
    REPORT: "asset_ranking",
    CONVERSATIONAL: "conversational",
}

MAINTENANCE_INTENTS = {
    DIAGNOSTIC,
    RISK,
    MAINTENANCE_PLANNING,
    INVENTORY,
    SOP,
    FAILURE_SIMULATION,
    ASSET_RANKING,
    BUSINESS_IMPACT,
    REPORT,
}

# Strict intent → specialist agents (synthesizer always follows; no dependency expansion in chat mode)
INTENT_AGENT_PLANS: dict[str, list[str]] = {
    ASSET_RANKING: [],
    BUSINESS_IMPACT: ["predictive_agent", "production_impact_agent"],
    DIAGNOSTIC: ["predictive_agent", "rca_agent"],
    FAILURE_SIMULATION: ["inventory_agent", "scenario_agent"],
    MAINTENANCE_PLANNING: ["predictive_agent", "inventory_agent", "planner_agent"],
    INVENTORY: ["inventory_agent"],
    SOP: ["document_agent"],
    RISK: ["predictive_agent", "risk_agent", "production_impact_agent"],
    REPORT: [],
    CONVERSATIONAL: [],
}

_GREETINGS = {
    "hi", "hello", "hey", "hii", "hola", "help", "thanks", "thank you",
    "ok", "okay", "bye", "goodbye", "good morning", "good afternoon", "good evening",
}

_CONVERSATIONAL_PATTERNS = (
    r"\btoday'?s date\b",
    r"\bwhat(?:'s| is) (?:the )?date\b",
    r"\bcurrent date\b",
    r"\bwhat day is (?:it|today)\b",
    r"\bwhat time is it\b",
    r"\bwho are you\b",
    r"\bwhat are you\b",
    r"\bwhat can you do\b",
    r"\bhow do you work\b",
    r"\bthank you\b",
    r"\bthanks\b",
    r"\bweather\b",
    r"\btell me a joke\b",
    r"\bhow old are you\b",
)


def normalize_message(message: str) -> str:
    cleaned = re.sub(r"\[Context:[^\]]+\]\s*", "", message, flags=re.IGNORECASE).strip()
    return cleaned or message.strip()


def is_conversational_intent(intent: str) -> bool:
    return intent == CONVERSATIONAL


def is_maintenance_intent(intent: str) -> bool:
    return intent in MAINTENANCE_INTENTS


def _is_greeting(text: str) -> bool:
    m = text.strip().lower()
    if m in _GREETINGS:
        return True
    if len(m) <= 25 and m.rstrip(".!?") in _GREETINGS:
        return True
    if len(m) <= 15 and any(m.startswith(w) for w in ("hi", "hey", "hello")):
        return True
    return False


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(p, text) for p in patterns)


GLOSSARY_TERMS = ("rul", "sop", "rca", "c-mapss", "cmapss", "ml", "kpi", "pm", "mtbf", "fmea", "ai")

_DEFINITION_PATTERNS = (
    r"\bfull form\b",
    r"\bfullform\b",
    r"\bstands? for\b",
    r"\bmeaning of\b",
    r"\bwhat does .* mean\b",
    r"\babbreviation\b",
    r"\bacronym\b",
    r"\bexpand\b",
)


def is_definition_query(message: str) -> bool:
    """Detect 'what is the full form of RUL' / 'what does SOP mean' style questions."""
    m = normalize_message(message).lower()
    has_term = any(re.search(rf"\b{re.escape(t)}\b", m) for t in GLOSSARY_TERMS)
    if not has_term:
        return False
    if _matches_any(m, _DEFINITION_PATTERNS):
        return True
    # "what is rul" / "define sop" (without 'the') → definition, not a value lookup
    if re.search(r"\bwhat(?:'s| is)\s+(?:a |an )?(rul|sop|rca|c-?mapss|ml|kpi|pm|mtbf|fmea)\b", m):
        return True
    if re.search(r"\bdefine\b", m):
        return True
    return False


def classify_chat_intent(message: str) -> str:
    """Classify into a maintenance intent — order matters (most specific first)."""
    m = normalize_message(message).lower()

    if _is_greeting(m):
        return CONVERSATIONAL

    if _matches_any(m, _CONVERSATIONAL_PATTERNS):
        return CONVERSATIONAL

    # Definition / glossary ("full form of RUL", "what does SOP mean") → conversational, not a diagnostic
    if is_definition_query(message):
        return CONVERSATIONAL

    # Fleet ranking — before single-asset RUL (e.g. "rank all assets by RUL")
    if any(w in m for w in ("rank", "ranking", "compare all", "all assets", "all 5", "every asset", "across the fleet")) and (
        "rul" in m or "remaining" in m or "life" in m or "asset" in m
        or "fleet" in m or "risk" in m or "priority" in m or "health" in m or "unit" in m
    ):
        return ASSET_RANKING

    # RUL — before navigation (queries like "what's the RUL?")
    if any(w in m for w in ("rul", "remaining useful life", "remaining life", "life left")):
        return DIAGNOSTIC

    # SOP / knowledge retrieval — before navigation ("show me SOP section" is NOT "go to documents")
    if any(w in m for w in (
        "sop", "standard operating", "manual", "procedure", "work instruction",
        "inspection steps", "inspection step",
    )) and any(w in m for w in ("show", "find", "section", "relevant", "lookup", "excerpt", "what", "where")):
        return SOP

    from app.services.portal_navigation import is_navigation_query

    if is_navigation_query(message):
        return CONVERSATIONAL

    # Maintenance action / urgency — before meta short-query heuristics
    if any(w in m for w in (
        "what should we do", "what to do", "what do we do", "what do we do next",
        "recommended action", "how to fix", "how do we fix", "given current sensors",
    )):
        return MAINTENANCE_PLANNING

    if _matches_any(m, (r"\bhow urgent\b", r"\burgency\b", r"\bhow soon\b", r"\bwhen should we act\b", r"\bwhen to act\b")):
        return MAINTENANCE_PLANNING

    # Safety / operability — "is it safe to run X", "can we keep running" → risk assessment
    if _matches_any(m, (
        r"\bsafe to (?:run|keep|operate|continue|push)\b",
        r"\bkeep running\b",
        r"\bcontinue running\b",
        r"\bcan we (?:run|operate|keep|continue)\b",
        r"\bis it safe\b",
        r"\boperate safely\b",
        r"\bsafe to (?:keep )?running\b",
    )):
        return RISK

    from app.services.meta_chat import is_meta_conversational

    if is_meta_conversational(message):
        return CONVERSATIONAL

    maintenance_signals = (
        "rul", "remaining useful life", "degrad", "diagnos", "fault", "failure",
        "root cause", "risk", "delay", "maintenance", "spare", "inventory", "procure",
        "sop", "manual", "procedure", "simulate", "scenario", "cascade", "downtime",
        "bearing", "vibration", "sensor", "equipment", "asset", "bf-001", "fleet",
        "report", "summary", "plan", "schedule", "alert", "health", "inspect",
        "rank", "production", "revenue", "critical",
    )
    if len(m.split()) <= 8 and not any(sig in m for sig in maintenance_signals):
        if _matches_any(m, (r"\bwhat is\b", r"\bhow many\b", r"\bdefine\b", r"\bexplain\b")):
            if not any(sig in m for sig in maintenance_signals):
                return CONVERSATIONAL

    # Failure simulation — deferral / sensor what-if (before business impact)
    if any(w in m for w in ("delay", "postpone", "defer", "wait")) and (
        "if" in m or "what" in m or "happens" in m
    ):
        return FAILURE_SIMULATION
    if any(w in m for w in (
        "what happens if", "what if", "happens if", "another shift",
        "unavailable", "increases by", "reaches", "run another",
        "maintenance is delayed", "delayed by",
    )):
        return FAILURE_SIMULATION

    # Asset ranking — fleet RUL comparison
    if any(w in m for w in ("rank", "ranking", "order by rul", "compare all", "all assets")) and (
        "rul" in m or "remaining" in m or "life" in m or "assets" in m
    ):
        return ASSET_RANKING
    if "rank" in m and any(w in m for w in ("asset", "fleet", "unit", "equipment")):
        return ASSET_RANKING

    # Business impact — production loss / fails now
    if any(w in m for w in (
        "production loss", "revenue", "cost exposure", "business impact",
        "how much", "financial impact", "downtime cost", "fails now", "fail now",
    )) and any(w in m for w in ("fail", "loss", "production", "downtime", "cost", "impact")):
        return BUSINESS_IMPACT
    if "if" in m and any(w in m for w in ("fail", "fails")) and any(
        w in m for w in ("production", "loss", "cost", "impact", "downtime")
    ):
        return BUSINESS_IMPACT

    # SOP / knowledge
    if any(w in m for w in (
        "sop", "standard operating", "manual", "procedure", "how to inspect",
        "inspection steps", "work instruction", "document", "find sop",
    )):
        return SOP

    # Critical spares / inventory
    if any(w in m for w in ("critical", "stockout", "reorder")) and any(
        w in m for w in ("spare", "part", "inventory", "stock")
    ):
        return INVENTORY
    if any(w in m for w in (
        "spare", "procure", "inventory", "stock", "reorder", "part number",
        "parts should", "parts to order", "lead time", "availability",
    )):
        return INVENTORY

    if any(w in m for w in (
        "what should we do", "what to do", "what do we do", "recommended action",
        "next step", "how to fix", "how do we fix",
    )):
        return MAINTENANCE_PLANNING

    if _matches_any(m, (r"\bhow urgent\b", r"\burgency\b", r"\bhow soon\b", r"\bwhen should we act\b", r"\bwhen to act\b")):
        return MAINTENANCE_PLANNING

    if _matches_any(m, (r"\bwhat is the fastest\b", r"\bfastest way\b", r"\bnext step\b")):
        return MAINTENANCE_PLANNING

    if any(w in m for w in (
        "maintenance plan", "7-day", "7 day", "next week", "schedule work",
        "action plan", "what should we do", "immediate action", "next steps",
        "when should we", "manpower",
    )):
        return MAINTENANCE_PLANNING

    # Root cause / diagnostic — before broad conversational fallthrough
    if any(w in m for w in (
        "analyze", "analyse", "degrad", "degradation", "degrading", "degraded",
    )):
        return DIAGNOSTIC

    # Root cause / diagnostic
    if any(w in m for w in (
        "root cause", "root-cause", "why is", "why did", "failure mode", "symptom",
        "degrad", "degration", "degradation", "degrading", "degraded",
        "diagnos", "fault", "failure analysis", "analyze", "analyse",
    )):
        return DIAGNOSTIC

    # Risk (non-scenario)
    if any(w in m for w in ("risk", "operational risk")):
        return RISK

    # Fleet reports → asset ranking view
    if any(w in m for w in (
        "fleet", "all 5", "overview", "summarize", "summary", "report", "brief",
    )):
        return ASSET_RANKING

    # Any explicit equipment code (RM-002, CP-003, …) → treat as asset diagnostic, never casual chat
    if re.search(r"\b[a-z]{2,3}-\d{2,3}\b", m):
        return DIAGNOSTIC

    if not any(sig in m for sig in maintenance_signals):
        return CONVERSATIONAL

    return DIAGNOSTIC


def conversational_answer(message: str, *, equipment_code: str = "your asset") -> str:
    """Direct answer for general conversational queries — no agent pipeline."""
    m = normalize_message(message).lower()
    now = datetime.now(timezone.utc)

    if _is_greeting(m):
        return (
            "Hello! I'm **ForgeMind**, your agentic AI assistant for steel-plant equipment.\n\n"
            f"Select an asset (e.g. **{equipment_code}**) and ask about diagnostics, RUL, risk, "
            "spares, maintenance plans, or SOPs."
        )

    if _matches_any(m, (r"\btoday'?s date\b", r"\bwhat(?:'s| is) (?:the )?date\b", r"\bcurrent date\b", r"\bwhat day is")):
        return f"Today is **{now.strftime('%A, %B %d, %Y')}** (UTC)."

    if re.search(r"\bwhat time is it\b", m):
        return f"The current time is **{now.strftime('%H:%M')} UTC**."

    if _matches_any(m, (r"\bwho are you\b", r"\bwhat are you\b")):
        return (
            "I'm **ForgeMind** — an agentic AI assistant for Tata Steel plant maintenance. "
            "I understand your intent first, then reason across sensors, ML, and plant knowledge to answer."
        )

    if _matches_any(m, (r"\bwhat can you do\b", r"\bhow do you work\b")):
        return (
            "I classify your question, then run only the relevant specialist agents:\n"
            "- **Asset Ranking** — fleet RUL comparison\n"
            "- **Business Impact** — downtime, production loss, ROI\n"
            "- **Root Cause** — diagnostic chain and sensor evidence\n"
            "- **Maintenance Planning** — actions, manpower, spares\n"
            "- **SOP / Knowledge** — manuals and procedures\n"
            "- **Failure Simulation** — deferral and what-if scenarios"
        )

    if _matches_any(m, (r"\bthank", r"\bthanks\b")):
        return "You're welcome! Ask anytime about your selected equipment."

    return (
        "That's outside plant maintenance scope, so I won't run equipment agents for this.\n\n"
        "Ask me about **fleet ranking**, **business impact**, **root cause**, **maintenance plans**, "
        "**critical spares**, **SOPs**, or **failure simulations**."
    )
