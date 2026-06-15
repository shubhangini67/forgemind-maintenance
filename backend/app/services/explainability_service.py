"""Assemble explainability bundle for decision-support UI."""

from __future__ import annotations

import time
from typing import Any

from app.services.agents.intent_classifier import INTENT_LABELS, RESPONSE_TEMPLATE_BY_INTENT

_ALLOWED_KNOWLEDGE_TYPES = {
    "manual",
    "sop",
    "procedure",
    "failure_report",
    "maintenance_record",
    "document",
    "report",
}
_BLOCKED_KNOWLEDGE_MARKERS = (
    "logbook",
    "ai analysis",
    "chat transcript",
    "conversation",
    "generated entry",
)


def _cap_pct(value: float | int | None, default: float = 0) -> float:
    try:
        n = float(value if value is not None else default)
    except (TypeError, ValueError):
        return default
    if n > 1 and n <= 100:
        return min(100.0, n)
    if n <= 1:
        return min(100.0, n * 100)
    return min(100.0, n)


def _is_allowed_knowledge(item: dict) -> bool:
    doc_type = str(item.get("document_type") or "document").lower()
    source = str(item.get("source") or "").lower()
    if doc_type in ("logbook", "chat", "ai_generated", "conversation"):
        return False
    if any(marker in source for marker in _BLOCKED_KNOWLEDGE_MARKERS):
        return False
    if doc_type not in _ALLOWED_KNOWLEDGE_TYPES and "manual" not in source and "sop" not in source:
        if "failure" not in source and "report" not in source:
            return doc_type == "document"
    return True


def _priority_label(risk_level: str | None, rul_hours: float | None) -> str:
    rl = str(risk_level or "medium").lower()
    rul = float(rul_hours or 999)
    if rl == "critical" or rul < 48:
        return "P1"
    if rl == "high" or rul < 168:
        return "P2"
    if rl == "medium":
        return "P3"
    return "P4"


def _format_rul_display(rul_hours: float | None) -> str:
    if rul_hours is None:
        return "—"
    rul = float(rul_hours)
    if rul >= 72:
        return f"{rul / 24:.1f} days"
    return f"{rul:.0f}h"


def build_root_cause_chain(
    *,
    diagnosis: dict | None,
    sensor_reading: dict | None,
    operational_context: dict | None,
) -> dict[str, Any]:
    reading = sensor_reading or {}
    diag = diagnosis or {}
    causes = diag.get("probable_causes") or []
    op = operational_context or {}

    temp = float(reading.get("temperature") or 70)
    vib = float(reading.get("vibration") or 3)
    health = float(reading.get("health_indicator") or 60)
    baseline_temp = 72.0
    baseline_vib = 3.2

    evidence: list[dict] = []
    if temp > baseline_temp:
        pct = round((temp - baseline_temp) / baseline_temp * 100)
        evidence.append({
            "label": f"Temperature increased {pct}%",
            "detail": f"Current {temp:.1f}°C vs baseline {baseline_temp:.0f}°C",
            "confidence_pct": _cap_pct(min(95, 70 + pct)),
        })
    if vib > baseline_vib:
        evidence.append({
            "label": "Vibration trend rising",
            "detail": f"Current {vib:.2f} mm/s vs nominal {baseline_vib:.1f} mm/s",
            "confidence_pct": 82,
        })
    for inc in (op.get("failure_incidents") or [])[:1]:
        evidence.append({
            "label": "Historical failure pattern match",
            "detail": inc.get("root_cause") or inc.get("description", "Similar incident on record"),
            "confidence_pct": 84,
        })
    if not evidence:
        evidence.append({
            "label": "C-MAPSS degradation signature",
            "detail": f"Health {health:.0f}% with sensor drift on FD001 curve",
            "confidence_pct": 76,
        })

    most_likely = causes[0]["cause"] if causes else "Bearing lubrication degradation"
    if "bearing" not in most_likely.lower() and vib >= 5:
        most_likely = "Bearing lubrication degradation"

    failure_path = [
        "Temperature Rise",
        "Bearing Friction",
        "Vibration Increase",
        "Bearing Wear",
        "Failure Risk",
    ]

    return {
        "title": "Root Cause Analysis",
        "evidence": evidence[:4],
        "most_likely_cause": most_likely,
        "failure_path": failure_path,
        "confidence_score": diag.get("confidence_score"),
    }


def build_knowledge_evidence(citations: list[dict] | None, rag_results: list[dict] | None) -> dict[str, Any]:
    items: list[dict] = []
    for c in (citations or [])[:6]:
        item = {
            "source": c.get("source", "Unknown"),
            "excerpt": (c.get("excerpt") or "")[:280],
            "document_type": c.get("document_type", "document"),
            "score": float(c.get("score") or 0),
            "reference": c.get("source", ""),
        }
        if _is_allowed_knowledge(item):
            items.append(item)
    for r in (rag_results or [])[:5]:
        if any(i["source"] == r.get("source") for i in items):
            continue
        item = {
            "source": r.get("source", "Unknown"),
            "excerpt": (r.get("excerpt") or "")[:280],
            "document_type": r.get("document_type", "document"),
            "score": float(r.get("score") or 0),
            "reference": r.get("source", ""),
        }
        if _is_allowed_knowledge(item):
            items.append(item)
    items = items[:4]
    avg_conf = _cap_pct(sum(i["score"] for i in items) / len(items) * 100 if items else 0)
    return {
        "title": "SOP & Manual References",
        "items": items,
        "confidence_pct": min(95.0, avg_conf) if items else 0,
    }


def build_decision_summary(
    *,
    current_state: dict,
    root_cause_chain: dict,
    risk_assessment: dict | None,
    maintenance_plan: dict | None,
    scenario_simulation: dict | None,
) -> dict[str, Any]:
    plan = maintenance_plan or {}
    sim = scenario_simulation or {}
    rcc = root_cause_chain or {}
    risk = risk_assessment or {}

    rul_hours = current_state.get("rul_hours")
    risk_level = str(current_state.get("risk_level") or risk.get("risk_level") or "medium").upper()
    fp = current_state.get("failure_probability_pct")
    root_cause = rcc.get("most_likely_cause") or "Under investigation"
    priority = _priority_label(risk_level, rul_hours)

    recommended = (
        sim.get("recommended_action")
        or (plan.get("immediate_actions") or [None])[0]
        or "Continue monitoring and schedule inspection per SOP"
    )

    return {
        "risk_level": risk_level,
        "rul": _format_rul_display(rul_hours),
        "rul_hours": rul_hours,
        "failure_probability_pct": fp,
        "root_cause": root_cause,
        "priority": priority,
        "recommended_action": recommended,
    }


def build_action_plan(maintenance_plan: dict | None) -> dict[str, list[str]]:
    plan = maintenance_plan or {}
    immediate = list(plan.get("immediate_actions") or [])[:5]
    next_shift = list(plan.get("short_term_actions") or [])[:5]
    long_term = list(plan.get("long_term_actions") or [])[:5]

    if not immediate:
        immediate = ["Inspect bearing housing", "Verify lubrication system"]
    if not next_shift:
        next_shift = ["Replace bearing assembly if vibration persists", "Check shaft alignment"]
    if not long_term:
        long_term = ["Increase vibration monitoring frequency", "Schedule predictive inspection"]

    return {
        "immediate": immediate,
        "next_shift": next_shift,
        "long_term": long_term,
    }


def build_executive_business_impact(
    *,
    business_impact: dict,
    production_impact: dict | None,
) -> dict[str, Any]:
    bi = business_impact or {}
    impact = production_impact or {}
    downtime = bi.get("estimated_downtime_hours") or impact.get("downtime_estimate_hours") or impact.get("expected_downtime_hours")
    tons = bi.get("estimated_production_loss_tons") or impact.get("throughput_impact_tons")
    exposure = bi.get("estimated_repair_cost_inr") or impact.get("business_cost_inr") or impact.get("downtime_cost_inr")
    savings = bi.get("potential_savings_inr") or impact.get("avoided_loss_inr")
    return {
        "downtime_avoided_hours": downtime,
        "production_protected_tons": tons,
        "cost_exposure_inr": exposure,
        "potential_savings_inr": savings,
    }


def build_agent_execution_trace(
    *,
    agent_thoughts: list[dict] | None,
    agent_trace: list[str] | None,
    execution_time_ms: float | None,
    query_intent: str | None,
) -> dict[str, Any]:
    agents: list[dict] = []
    seen: set[str] = set()
    for t in agent_thoughts or []:
        agent = t.get("agent", "")
        if agent in seen or agent in ("synthesizer",):
            continue
        seen.add(agent)
        agents.append({
            "agent": agent,
            "label": t.get("label") or agent.replace("_", " ").title(),
            "status": "complete",
            "phase": t.get("phase") or "",
        })

    data_sources = [
        "NASA C-MAPSS",
        "Maintenance History",
        "Spare Inventory",
        "Delay Logs",
        "SOP Documents",
    ]

    return {
        "title": "Agent Execution Trace",
        "agents": agents,
        "execution_time_ms": round(execution_time_ms or 0, 1),
        "execution_time_s": round((execution_time_ms or 0) / 1000, 2),
        "data_sources": data_sources,
        "query_intent": query_intent,
        "intent_label": INTENT_LABELS.get(query_intent or "", query_intent),
        "trace_lines": agent_trace or [],
    }


def build_explainability_bundle(
    *,
    structured_output: dict[str, Any],
    sensor_reading: dict | None,
    operational_context: dict | None,
    agent_thoughts: list[dict] | None,
    agent_trace: list[str] | None,
    citations: list[dict] | None,
    execution_time_ms: float | None,
    query_intent: str | None,
    scenario_simulation: dict | None = None,
) -> dict[str, Any]:
    pred = structured_output.get("prediction") or {}
    risk = structured_output.get("risk_assessment") or {}
    inv = structured_output.get("inventory_assessment") or {}
    impact = structured_output.get("production_impact") or {}
    scenario = scenario_simulation or structured_output.get("scenario_simulation") or {}

    current_state = scenario.get("current_state") or {
        "rul_hours": pred.get("remaining_useful_life_hours"),
        "failure_probability_pct": round(float(pred.get("failure_probability") or 0) * 100, 1),
        "health_score": sensor_reading.get("health_indicator") if sensor_reading else None,
        "risk_level": risk.get("risk_level"),
        "risk_score_100": (risk.get("score_breakdown") or {}).get("final_score_100"),
        "spare_stock": inv.get("spare_stock"),
        "lead_time_days": inv.get("lead_time_days"),
    }

    business = scenario.get("business_impact") or {
        "estimated_downtime_hours": impact.get("downtime_estimate_hours") or impact.get("expected_downtime_hours"),
        "estimated_production_loss_tons": impact.get("throughput_impact_tons"),
        "estimated_repair_cost_inr": impact.get("business_cost_inr") or impact.get("downtime_cost_inr"),
        "preventive_maintenance_cost_inr": impact.get("maintenance_cost_inr", 40000),
        "potential_savings_inr": impact.get("avoided_loss_inr"),
    }

    intent_response = structured_output.get("intent_response") or {}
    template = structured_output.get("response_template") or RESPONSE_TEMPLATE_BY_INTENT.get(
        query_intent or "", "root_cause_analysis"
    )
    agents_invoked = [
        t.get("agent") for t in (agent_thoughts or [])
        if t.get("agent") not in ("synthesizer", "supervisor")
    ]

    routing_log = {
        "detected_intent": query_intent,
        "intent_label": INTENT_LABELS.get(query_intent or "", query_intent),
        "response_template": template,
        "agents_invoked": agents_invoked,
    }

    root_cause_chain = build_root_cause_chain(
        diagnosis=structured_output.get("diagnosis"),
        sensor_reading=sensor_reading,
        operational_context=operational_context,
    )
    knowledge_evidence = build_knowledge_evidence(
        citations,
        structured_output.get("rag_results") or [],
    )
    agent_trace_bundle = build_agent_execution_trace(
        agent_thoughts=agent_thoughts,
        agent_trace=agent_trace,
        execution_time_ms=execution_time_ms,
        query_intent=query_intent,
    )

    base = {
        "query_intent": query_intent,
        "response_template": template,
        "routing_log": routing_log,
        "intent_response": intent_response,
        "root_cause_chain": root_cause_chain,
        "knowledge_evidence": knowledge_evidence,
        "agent_trace": agent_trace_bundle,
    }

    if template == "asset_ranking":
        return {**base, "asset_ranking": intent_response}
    if template == "business_impact":
        return {**base, "business_impact_detail": intent_response}
    if template == "root_cause_analysis":
        return {**base, "root_cause_analysis": intent_response}
    if template == "maintenance_plan":
        return {**base, "maintenance_plan_detail": intent_response}
    if template == "sop_knowledge":
        return {**base, "sop_knowledge": intent_response}
    if template == "critical_spares":
        return {**base, "critical_spares": intent_response}
    if template == "failure_simulation":
        sim = scenario_simulation or structured_output.get("scenario_simulation") or intent_response.get("scenario_simulation") or {}
        return {**base, "scenario_simulation": sim, "failure_simulation": intent_response}

    # Legacy fallback — generic decision card (avoid for chat intents)
    current_state = scenario.get("current_state") or {
        "rul_hours": pred.get("remaining_useful_life_hours"),
        "failure_probability_pct": round(float(pred.get("failure_probability") or 0) * 100, 1),
        "health_score": sensor_reading.get("health_indicator") if sensor_reading else None,
        "risk_level": risk.get("risk_level"),
    }
    return {
        **base,
        "decision_summary": build_decision_summary(
            current_state=current_state,
            root_cause_chain=root_cause_chain,
            risk_assessment=risk,
            maintenance_plan=structured_output.get("maintenance_plan"),
            scenario_simulation=scenario,
        ),
    }
