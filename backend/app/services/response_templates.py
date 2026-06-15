"""Intent-specific response templates — each intent produces a distinct structure."""

from __future__ import annotations

from typing import Any

from app.services.agents.intent_classifier import (
    ASSET_RANKING,
    BUSINESS_IMPACT,
    DIAGNOSTIC,
    FAILURE_SIMULATION,
    INVENTORY,
    INTENT_LABELS,
    MAINTENANCE_PLANNING,
    RESPONSE_TEMPLATE_BY_INTENT,
    SOP,
)
from app.services.scenario_simulation_engine import build_simulation_markdown, run_scenario_simulation


def _fmt_inr(amount: int | float) -> str:
    n = int(amount or 0)
    if n == 0:
        return "₹0"
    if n >= 100_000:
        return f"₹{n / 100_000:.1f} Lakhs"
    if n >= 1_000:
        return f"₹{round(n / 1_000)}k"
    return f"₹{n:,}"


def _risk_str(level: Any) -> str:
    if hasattr(level, "value"):
        level = level.value
    return str(level or "medium").replace("_", " ").title()


def _priority_from_rul_risk(rul_hours: float | None, risk: str) -> str:
    rl = risk.lower()
    rul = float(rul_hours or 999)
    if rl == "critical" or rul < 48:
        return "P1"
    if rl == "high" or rul < 168:
        return "P2"
    if rl == "medium":
        return "P3"
    return "P4"


def build_asset_ranking(state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    fleet = state.get("fleet_snapshot") or {}
    assets = list(fleet.get("assets") or [])
    query = state.get("query") or ""

    ranked = sorted(
        assets,
        key=lambda a: float(a.get("rul_hours") or 0),
    )
    rows = []
    for i, a in enumerate(ranked, 1):
        rul = float(a.get("rul_hours") or 0)
        fp = float(a.get("failure_probability") or 0) * 100
        risk = _risk_str(a.get("risk_level"))
        priority = _priority_from_rul_risk(rul, risk)
        rows.append({
            "rank": i,
            "equipment_code": a.get("equipment_code"),
            "name": a.get("name"),
            "rul_hours": round(rul, 1),
            "rul_display": f"{rul / 24:.1f} days" if rul >= 72 else f"{rul:.0f}h",
            "failure_probability_pct": round(fp, 1),
            "risk_level": risk,
            "priority": priority,
            "health_score": a.get("health_score"),
        })

    urgent = ranked[0] if ranked else None
    rec = (
        f"Prioritize **{urgent.get('equipment_code')}** — lowest RUL ({float(urgent.get('rul_hours') or 0):.0f}h) "
        f"with {_risk_str(urgent.get('risk_level'))} risk."
        if urgent
        else "No fleet assets available for ranking."
    )

    lines = [
        "## Asset Ranking by Remaining Useful Life",
        "",
        f"**Query:** {query}",
        "",
        "| Rank | Asset | RUL | Failure Prob | Risk | Priority |",
        "|------|-------|-----|----------------|------|----------|",
    ]
    for r in rows:
        lines.append(
            f"| {r['rank']} | {r['equipment_code']} | {r['rul_display']} | {r['failure_probability_pct']}% "
            f"| {r['risk_level']} | {r['priority']} |"
        )
    lines.extend(["", "### Maintenance Priority Recommendation", "", rec])

    payload = {"ranked_assets": rows, "recommendation": rec, "total_assets": len(rows)}
    return "\n".join(lines), payload


def build_business_impact(state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    eq = state.get("equipment_context") or {}
    code = eq.get("equipment_code", "Asset")
    impact = state.get("production_impact") or {}
    pred = state.get("ml_prediction") or {}
    query = state.get("query") or ""

    downtime_h = float(impact.get("downtime_estimate_hours") or impact.get("expected_downtime_hours") or 16)
    tons = float(impact.get("throughput_impact_tons") or 0)
    exposure = int(impact.get("business_cost_inr") or impact.get("downtime_cost_inr") or 0)
    repair = int(impact.get("maintenance_cost_inr") or 40_000)
    savings = int(impact.get("avoided_loss_inr") or max(0, exposure - repair))
    roi_pct = round((savings / max(repair, 1)) * 100) if repair else 0
    fp = float(pred.get("failure_probability") or 0) * 100

    payload = {
        "equipment_code": code,
        "downtime_estimate_hours": round(downtime_h, 1),
        "production_loss_tons": tons,
        "revenue_exposure_inr": exposure,
        "repair_cost_inr": repair,
        "preventive_roi_pct": roi_pct,
        "potential_savings_inr": savings,
        "failure_probability_pct": round(fp, 1),
    }

    lines = [
        f"## Business Impact — {code}",
        "",
        f"**Query:** {query}",
        "",
        "| Metric | Estimate |",
        "|--------|----------|",
        f"| Estimated Downtime | **{downtime_h:.0f} hours** |",
        f"| Production Loss | **{tons:.0f} tons** |",
        f"| Revenue / Cost Exposure | **{_fmt_inr(exposure)}** |",
        f"| Repair Cost (if failure occurs) | **{_fmt_inr(repair)}** |",
        f"| ROI of Preventive Maintenance | **{roi_pct}%** ({_fmt_inr(savings)} avoided loss) |",
        f"| Failure Probability (now) | **{fp:.1f}%** |",
        "",
        "### Summary",
        "",
        f"If **{code}** fails now, expect **{downtime_h:.0f}h** downtime, **{tons:.0f} tons** production loss, "
        f"and **{_fmt_inr(exposure)}** exposure. Preventive action costing **{_fmt_inr(repair)}** "
        f"could protect **{_fmt_inr(savings)}** in avoided losses.",
    ]
    return "\n".join(lines), payload


def build_root_cause(state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    eq = state.get("equipment_context") or {}
    code = eq.get("equipment_code", "Asset")
    diag = state.get("diagnosis") or {}
    pred = state.get("ml_prediction") or {}
    reading = state.get("sensor_reading") or {}
    query = state.get("query") or ""
    rcc = diag.get("root_cause_chain") or {}
    causes = diag.get("probable_causes") or []
    fp = float(pred.get("failure_probability") or 0) * 100

    path = rcc.get("failure_path") or []
    evidence = rcc.get("evidence") or []
    most_likely = rcc.get("most_likely_cause") or (causes[0]["cause"] if causes else "Under investigation")

    sensor_evidence = [
        f"Temperature: {reading.get('temperature', '—')}°C",
        f"Vibration: {reading.get('vibration', '—')} mm/s",
        f"Health: {reading.get('health_indicator', '—')}%",
        f"C-MAPSS cycle: {reading.get('cycle', '—')}",
    ]

    lines = [
        f"## Root Cause Analysis — {code}",
        "",
        f"**Query:** {query}",
        "",
        f"**Most Likely Cause:** {most_likely}",
        f"**Failure Probability:** {fp:.1f}%",
        "",
        "### Root Cause Chain",
        "",
    ]
    if path:
        lines.append(" → ".join(path))
    else:
        lines.append("Sensor drift → Component wear → Failure risk escalation")

    lines.extend(["", "### Sensor Evidence", ""])
    for s in sensor_evidence:
        lines.append(f"- {s}")
    if evidence:
        lines.extend(["", "### Historical / Pattern Evidence", ""])
        for ev in evidence:
            lines.append(f"- {ev.get('label', '')}: {ev.get('detail', '')}")

    payload = {
        "most_likely_cause": most_likely,
        "failure_path": path,
        "sensor_evidence": sensor_evidence,
        "pattern_evidence": evidence,
        "failure_probability_pct": round(fp, 1),
        "probable_causes": causes[:4],
    }
    return "\n".join(lines), payload


def build_maintenance_plan(state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    eq = state.get("equipment_context") or {}
    code = eq.get("equipment_code", "Asset")
    plan = state.get("maintenance_plan") or {}
    inv = state.get("inventory_assessment") or {}
    pred = state.get("ml_prediction") or {}
    reading = state.get("sensor_reading") or {}
    query = state.get("query") or ""
    q = query.lower()

    immediate = plan.get("immediate_actions") or []
    next_shift = plan.get("short_term_actions") or []
    long_term = plan.get("long_term_actions") or []
    spares = inv.get("spares") or state.get("spare_context") or []

    rul = float(reading.get("rul_hours") or pred.get("remaining_useful_life_hours") or 999)
    fp = float(pred.get("failure_probability") or 0) * 100
    if rul < 48 or fp > 65 or "urgent" in q:
        urgency = "**CRITICAL — act within 24–48 hours**"
        window = "Schedule intervention before next shift ends."
    elif rul < 168 or fp > 45:
        urgency = "**HIGH — act within 3–5 days**"
        window = "Plan shutdown window this week; stage spares now."
    else:
        urgency = "**MODERATE — plan within 2 weeks**"
        window = "Include in next PM cycle; continue monitoring."

    if not immediate:
        immediate = [
            "Inspect bearing assembly and lubrication within 4h",
            "Verify vibration trend against baseline",
            "Confirm spare parts staged before next shift",
        ]

    manpower = "2 maintenance technicians + 1 reliability engineer (4h window)"
    if any("stop" in a.lower() for a in immediate):
        manpower = "3 technicians + shift supervisor — emergency window"

    required_spares = [
        f"{s.get('part_number', 'N/A')} — {s.get('name', 'Part')} ({s.get('quantity_available', 0)} in stock)"
        for s in spares[:4]
    ] or ["Verify bearing kit and lubricant stock before shift"]

    payload = {
        "immediate_actions": immediate,
        "next_shift_actions": next_shift,
        "long_term_actions": long_term,
        "required_manpower": manpower,
        "required_spares": required_spares,
        "urgency_level": urgency,
        "action_window": window,
        "rul_hours": round(rul, 1),
        "failure_probability_pct": round(fp, 1),
    }

    lines = [
        f"## Maintenance Plan — {code}",
        "",
        f"**Query:** {query}",
        "",
        "### Urgency Assessment",
        "",
        urgency,
        window,
        f"RUL: **{rul:.0f}h** · Failure probability: **{fp:.1f}%**",
        "",
        "### Immediate Actions",
        "",
    ]
    lines.extend(f"- {a}" for a in immediate) or lines.append("- Monitor and inspect per SOP")
    lines.extend(["", "### Next Shift Actions", ""])
    lines.extend(f"- {a}" for a in next_shift) or lines.append("- Schedule corrective maintenance if degradation persists")
    lines.extend(["", "### Long-Term Actions", ""])
    lines.extend(f"- {a}" for a in long_term) or lines.append("- Increase predictive monitoring frequency")
    lines.extend(["", "### Required Manpower", "", manpower, "", "### Required Spares", ""])
    lines.extend(f"- {s}" for s in required_spares)

    return "\n".join(lines), payload


def build_sop_knowledge(state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    eq = state.get("equipment_context") or {}
    code = eq.get("equipment_code", "Asset")
    rag = state.get("rag_results") or []
    query = state.get("query") or ""

    docs = []
    for r in rag[:4]:
        dt = str(r.get("document_type", "document")).lower()
        src = str(r.get("source", "")).lower()
        if dt in ("logbook", "chat", "ai_generated") or "logbook" in src:
            continue
        docs.append({
            "source": r.get("source"),
            "document_type": r.get("document_type"),
            "excerpt": (r.get("excerpt") or "")[:320],
            "reference": r.get("source"),
        })

    procedure_steps = []
    safety_notes = []
    for d in docs:
        excerpt = d.get("excerpt") or ""
        for line in excerpt.split("\n"):
            line = line.strip()
            if not line:
                continue
            if any(w in line.lower() for w in ("warning", "caution", "safety", "ppe", "lockout")):
                safety_notes.append(line[:200])
            elif line[0].isdigit() or line.startswith("-"):
                procedure_steps.append(line[:200])
    if not procedure_steps:
        procedure_steps = [
            "1. Isolate equipment and verify lockout/tagout",
            "2. Inspect bearing housing and lubrication points",
            "3. Record vibration and temperature readings in logbook",
        ]
    if not safety_notes:
        safety_notes = [
            "Use mandatory PPE — heat-resistant gloves and face shield near running equipment",
            "Follow LOTO procedure before physical inspection",
        ]

    payload = {
        "documents": docs,
        "procedure_steps": procedure_steps[:6],
        "safety_notes": safety_notes[:4],
    }

    lines = [
        f"## SOP & Knowledge — {code}",
        "",
        f"**Query:** {query}",
        "",
        "### Relevant Documents",
        "",
    ]
    if docs:
        for d in docs:
            lines.append(f"- **{d['source']}** ({d.get('document_type', 'document')})")
            lines.append(f"  > {d['excerpt'][:180]}…")
    else:
        lines.append("- No matching SOP/manual found — index reference documents in Knowledge base.")

    lines.extend(["", "### Procedure Steps", ""])
    lines.extend(f"- {s}" for s in procedure_steps[:6])
    lines.extend(["", "### Safety Notes", ""])
    lines.extend(f"- {n}" for n in safety_notes[:4])

    return "\n".join(lines), payload


def build_critical_spares(state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    eq = state.get("equipment_context") or {}
    code = eq.get("equipment_code", "Asset")
    inv = state.get("inventory_assessment") or {}
    spares = inv.get("spares") or state.get("spare_context") or []
    all_spares = (state.get("fleet_snapshot") or {}).get("critical_spares") or spares
    query = state.get("query") or ""

    critical = []
    for s in all_spares:
        qty = int(s.get("quantity_available", 0))
        reorder = int(s.get("reorder_level", 5))
        lead = int(s.get("lead_time_days", 14))
        criticality = "CRITICAL" if qty == 0 else "HIGH" if qty <= reorder else "MEDIUM"
        if criticality in ("CRITICAL", "HIGH"):
            critical.append({
                "part_number": s.get("part_number"),
                "name": s.get("name"),
                "quantity_available": qty,
                "reorder_level": reorder,
                "lead_time_days": lead,
                "criticality": criticality,
                "equipment_code": s.get("equipment_code", code),
            })

    lines = [
        "## Critical Spare Parts",
        "",
        f"**Query:** {query}",
        "",
        "| Part | Stock | Reorder | Lead Time | Status |",
        "|------|-------|---------|-----------|--------|",
    ]
    for c in critical[:8]:
        lines.append(
            f"| {c.get('part_number')} {c.get('name', '')[:24]} | {c['quantity_available']} "
            f"| {c['reorder_level']} | {c['lead_time_days']}d | **{c['criticality']}** |"
        )
    if not critical:
        lines.append("| — | All mapped spares above reorder levels | — | — | OK |")

    rec = (
        f"Procure **{critical[0]['part_number']}** immediately — zero/low stock with {critical[0]['lead_time_days']}d lead time."
        if critical
        else "Spare stock levels are adequate across mapped critical parts."
    )
    lines.extend(["", "### Recommendation", "", rec])

    payload = {"critical_spares": critical, "recommendation": rec, "procurement_risk": inv.get("procurement_risk")}
    return "\n".join(lines), payload


def build_failure_simulation(state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    eq = state.get("equipment_context") or {}
    scenario = state.get("scenario_analysis") or {}
    sim = state.get("scenario_simulation") or scenario.get("simulation") or {}
    query = state.get("query") or ""

    if not sim.get("projections"):
        sim = run_scenario_simulation(
            query=query,
            equipment_context=eq,
            sensor_reading=state.get("sensor_reading") or {},
            spare_context=state.get("spare_context") or [],
            operational_context=state.get("operational_context") or {},
            force_standard_horizons=True,
        )

    markdown = sim.get("markdown_table") or build_simulation_markdown(
        sim,
        equipment_code=eq.get("equipment_code", "Asset"),
        equipment_name=eq.get("name", ""),
        query=query,
    )
    payload = {
        "scenario_simulation": sim,
        "recommended_action": sim.get("recommended_action"),
        "intervention_point": "+7 Days" if any(
            p.get("delay_days", 0) >= 7 for p in (sim.get("projections") or [])
        ) else "+3 Days",
    }
    return markdown, payload


_BUILDERS = {
    "asset_ranking": build_asset_ranking,
    "business_impact": build_business_impact,
    "root_cause_analysis": build_root_cause,
    "maintenance_plan": build_maintenance_plan,
    "sop_knowledge": build_sop_knowledge,
    "critical_spares": build_critical_spares,
    "failure_simulation": build_failure_simulation,
}


def synthesize_intent_response(state: dict[str, Any]) -> tuple[str, dict[str, Any], str]:
    """Return (markdown_message, intent_response_payload, response_template_id)."""
    from app.services.chat_response_formatter import format_chat_response

    intent = state.get("query_intent") or DIAGNOSTIC
    template = RESPONSE_TEMPLATE_BY_INTENT.get(intent, "root_cause_analysis")
    builder = _BUILDERS.get(template, build_root_cause)
    _, payload = builder(state)
    message = format_chat_response(state, template)
    return message, payload, template
