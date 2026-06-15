"""Portal navigation helpers — map natural language to in-app routes."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class PortalLink:
    href: str
    label: str
    description: str


PORTAL_ROUTES: list[PortalLink] = [
    PortalLink("/home", "Portal Home", "Landing hub and fleet overview"),
    PortalLink("/dashboard", "Dashboard", "KPIs, health summary, and alerts"),
    PortalLink("/monitor", "Live Monitor", "Real-time C-MAPSS sensor streams"),
    PortalLink("/equipment", "Equipment", "Asset registry and health details"),
    PortalLink("/chat", "Ask AI", "Maintenance copilot chat"),
    PortalLink("/diagnose", "Diagnose", "Fault analysis workspace"),
    PortalLink("/simulate", "Decision Simulator", "What-if failure scenarios"),
    PortalLink("/priority", "Priority Queue", "Ranked maintenance backlog"),
    PortalLink("/alerts", "Alerts", "Open and triaged plant alerts"),
    PortalLink("/scheduler", "Schedule", "Maintenance calendar"),
    PortalLink("/logbook", "Logbook", "Digital maintenance log"),
    PortalLink("/delays", "Delay Logs", "Schedule deviation history"),
    PortalLink("/spares", "Inventory", "Spare parts and stock levels"),
    PortalLink("/knowledge", "Documents", "SOPs and manuals"),
    PortalLink("/reports", "Reports", "Management reports"),
    PortalLink("/analytics", "Analytics", "ROI and degradation analytics"),
    PortalLink("/history", "History", "Past interventions"),
]

_ALIASES: dict[str, str] = {
    "live monitor": "/monitor",
    "monitor": "/monitor",
    "monitoring": "/monitor",
    "live sensors": "/monitor",
    "sensor stream": "/monitor",
    "dashboard": "/dashboard",
    "home": "/home",
    "portal": "/home",
    "equipment": "/equipment",
    "assets": "/equipment",
    "fleet": "/equipment",
    "chat": "/chat",
    "ai": "/chat",
    "ask ai": "/chat",
    "assistant": "/chat",
    "diagnose": "/diagnose",
    "diagnosis": "/diagnose",
    "simulator": "/simulate",
    "simulate": "/simulate",
    "decision simulator": "/simulate",
    "priority": "/priority",
    "priority queue": "/priority",
    "alerts": "/alerts",
    "schedule": "/scheduler",
    "scheduler": "/scheduler",
    "logbook": "/logbook",
    "delays": "/delays",
    "delay log": "/delays",
    "inventory": "/spares",
    "spares": "/spares",
    "spare parts": "/spares",
    "documents": "/knowledge",
    "knowledge": "/knowledge",
    "sop": "/knowledge",
    "manuals": "/knowledge",
    "reports": "/reports",
    "analytics": "/analytics",
    "history": "/history",
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


_MAINTENANCE_WORDS = (
    "degrad", "diagnos", "analyze", "analyse", "root cause", "rul", "failure",
    "sensor", "bearing", "vibration", "maint", "fault", "inspect", "spare",
)


def _alias_in_message(alias: str, message: str) -> bool:
    """Avoid false positives — 'analyze' must not match alias 'ai'."""
    if len(alias) <= 3:
        return bool(re.search(rf"\b{re.escape(alias)}\b", message))
    return alias in message


_KNOWLEDGE_QUERY_MARKERS = (
    "sop section", "relevant sop", "manual section", "show me the relevant",
    "show me the sop", "procedure for", "inspection step", "work instruction",
    "manual for", "sop for", "find sop", "find the sop",
)


def _is_knowledge_query(message: str) -> bool:
    m = _normalize(message)
    return any(k in m for k in _KNOWLEDGE_QUERY_MARKERS) or (
        any(w in m for w in ("sop", "manual", "procedure"))
        and any(w in m for w in ("show", "find", "section", "relevant", "lookup", "excerpt"))
    )


_DATA_QUERY_MARKERS = (
    "rate", "cost", "price", "per unit", "how much", "lead time", "stock",
    "quantity", "reorder", "rul", "remaining", "failure prob", "downtime",
    "health", "vibration", "temperature",
)


def is_navigation_query(message: str) -> bool:
    m = _normalize(message)
    if _is_knowledge_query(message):
        return False
    # Data lookups ("per unit rate", "how much", "lead time") are answered by agents, not navigation
    if any(d in m for d in _DATA_QUERY_MARKERS):
        return False
    if any(w in m for w in _MAINTENANCE_WORDS):
        triggers = (
            "where is", "where's", "where can i find", "how do i get to", "how to open",
            "take me to", "go to", "open ", "find the", "navigate to", "show me the",
            "link to", "page for",
        )
        return any(t in m for t in triggers)
    triggers = (
        "where is", "where's", "where can i find", "how do i get to", "how to open",
        "take me to", "go to", "open ", "find the", "navigate to", "show me the",
        "link to", "page for",
    )
    if any(t in m for t in triggers):
        return True
    return any(_alias_in_message(alias, m) for alias in _ALIASES)


def resolve_navigation(message: str) -> PortalLink | None:
    """Best-match portal route for a navigation question."""
    m = _normalize(message)
    best: PortalLink | None = None
    best_score = 0

    for alias, href in sorted(_ALIASES.items(), key=lambda x: -len(x[0])):
        if not _alias_in_message(alias, m):
            continue
        for route in PORTAL_ROUTES:
            if route.href == href:
                score = len(alias) + 10
                if score > best_score:
                    best, best_score = route, score
                break

    if best:
        return best

    for route in PORTAL_ROUTES:
        label = route.label.lower()
        if label in m or label.replace(" ", "") in m.replace(" ", ""):
            return route
    return None


def format_navigation_markdown(link: PortalLink, *, equipment_code: str | None = None) -> str:
    eq = f"?equipment={equipment_code}" if equipment_code and equipment_code not in ("your asset", "Asset") else ""
    href = f"{link.href}{eq}" if eq and "?" not in link.href else link.href
    return (
        f"**{link.label}** — {link.description.lower()}.\n\n"
        f"[Open {link.label}]({href})"
    )


def format_greeting_markdown(*, equipment_code: str | None = None, equipment_name: str = "") -> str:
    if equipment_code:
        name = f" ({equipment_name})" if equipment_name else ""
        return (
            f"Hello. I can help with **{equipment_code}**{name} — sensors, root cause, RUL, and maintenance actions. "
            f"Ask a specific question when you are ready."
        )
    return (
        "Hello. I am **ForgeMind**, your agentic AI copilot for Tata Steel maintenance. "
        "Ask about the plant, navigation, or switch to Asset mode for unit diagnostics."
    )
