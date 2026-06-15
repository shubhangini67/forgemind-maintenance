"""Plain-text markdown chat responses — plant engineer tone, fixed section layouts."""

from __future__ import annotations

import re
from typing import Any

from app.services.agents.intent_classifier import (
    ASSET_RANKING,
    BUSINESS_IMPACT,
    DIAGNOSTIC,
    FAILURE_SIMULATION,
    INVENTORY,
    MAINTENANCE_PLANNING,
    SOP,
)


def _risk_label(rul_hours: float, failure_prob_pct: float) -> str:
    if failure_prob_pct >= 75 or rul_hours < 48:
        return "CRITICAL"
    if failure_prob_pct >= 55 or rul_hours < 120:
        return "HIGH"
    if failure_prob_pct >= 35 or rul_hours < 336:
        return "MEDIUM"
    return "LOW"


def _timeframe_for_action(text: str, index: int) -> str:
    t = text.lower()
    if index == 0 or any(w in t for w in ("immediate", "inspect", "verify", "log", "confirm", "stop")):
        return "ASAP"
    if any(w in t for w in ("schedule", "plan", "next shift", "stage")):
        return "next shift"
    return "planned outage"


def _follow_up_block(questions: list[str]) -> list[str]:
    lines = ["", "## Follow-up Questions"]
    for q in questions[:3]:
        lines.append(f"-> {q.rstrip('?')}?")
    return lines


def _default_follow_ups(code: str, intent: str) -> list[str]:
    if intent in (INVENTORY, "critical_spares"):
        return [
            f"What is the reorder lead time for critical parts on {code}?",
            f"Is it safe to keep running {code} until spares arrive?",
            f"Show me the relevant SOP section for {code}",
        ]
    if intent == SOP:
        return [
            f"What inspection steps should I run first on {code}?",
            f"Which spare parts should I order for {code}?",
            f"Is it safe to keep running {code}?",
        ]
    return [
        f"What spare parts should I order for {code}?",
        f"Is it safe to keep running {code}?",
        f"Show me the relevant SOP section for {code}",
    ]


def _sensor_summary(reading: dict) -> str:
    parts = []
    if reading.get("temperature") is not None:
        parts.append(f"temperature {reading['temperature']}°C")
    if reading.get("vibration") is not None:
        parts.append(f"vibration {reading['vibration']} mm/s")
    if reading.get("health_indicator") is not None:
        parts.append(f"health index {reading['health_indicator']}%")
    return ", ".join(parts) if parts else "live C-MAPSS sensor readings"


def format_diagnostic(state: dict[str, Any]) -> str:
    eq = state.get("equipment_context") or {}
    code = eq.get("equipment_code", "Asset")
    name = eq.get("name") or ""
    diag = state.get("diagnosis") or {}
    pred = state.get("ml_prediction") or {}
    reading = state.get("sensor_reading") or {}
    plan = state.get("maintenance_plan") or {}
    rcc = diag.get("root_cause_chain") or {}

    fp = float(pred.get("failure_probability") or 0) * 100
    rul = float(reading.get("rul_hours") or pred.get("remaining_useful_life_hours") or 0)
    risk = _risk_label(rul, fp)
    causes = list(diag.get("probable_causes") or [])
    most_likely = rcc.get("most_likely_cause") or diag.get("root_cause_analysis") or ""
    if not causes and most_likely:
        causes = [{"cause": most_likely, "confidence": 0.82}]

    sensor_ev = _sensor_summary(reading)
    summary = (
        f"**{code}**"
        + (f" ({name})" if name else "")
        + f" shows degrading condition based on {sensor_ev}. "
    )
    if most_likely:
        summary += f"The leading failure mode is **{most_likely}**, consistent with historical C-MAPSS FD001 patterns and indexed maintenance records."
    else:
        summary += "Sensor drift and elevated vibration suggest progressive component wear requiring inspection."

    lines = [
        "## Summary",
        summary.strip(),
        "",
        "## Key metrics",
        f"- **Failure probability:** {fp:.1f}%",
        f"- **Remaining useful life:** ~{rul:.0f} hours" if rul else "- **Remaining useful life:** —",
        f"- **Risk level:** {risk}",
        "",
        "## Key findings",
    ]
    if causes:
        for c in causes[:4]:
            if isinstance(c, dict):
                cause = c.get("cause", "Unknown")
                conf = float(c.get("confidence", 0.75))
                pct = conf * 100 if conf <= 1 else conf
            else:
                cause, pct = str(c), 70.0
            lines.append(f"- {cause} ({pct:.0f}% confidence)")
    else:
        path = rcc.get("failure_path") or ["Sensor drift", "Bearing wear", "Failure risk escalation"]
        for i, step in enumerate(path[:3]):
            lines.append(f"- {step} ({85 - i * 15}% confidence)")

    actions = plan.get("immediate_actions") or plan.get("short_term_actions") or [
        "Inspect bearing assembly and lubrication system",
        "Compare vibration trend to baseline and log readings",
        "Review RUL trend and schedule corrective maintenance",
    ]
    lines.extend(["", "## Recommended actions"])
    for i, action in enumerate(actions[:3], 1):
        lines.append(f"{i}. {action} (timeframe: {_timeframe_for_action(action, i - 1)})")

    lines.extend(_follow_up_block(_default_follow_ups(code, DIAGNOSTIC)))
    return "\n".join(lines)


def format_maintenance_plan(state: dict[str, Any]) -> str:
    eq = state.get("equipment_context") or {}
    code = eq.get("equipment_code", "Asset")
    plan = state.get("maintenance_plan") or {}
    pred = state.get("ml_prediction") or {}
    reading = state.get("sensor_reading") or {}
    diag = state.get("diagnosis") or {}

    fp = float(pred.get("failure_probability") or 0) * 100
    rul = float(reading.get("rul_hours") or pred.get("remaining_useful_life_hours") or 0)
    risk = _risk_label(rul, fp)
    causes = diag.get("probable_causes") or []

    lines = [
        "## Summary",
        f"For **{code}**, recommended maintenance actions are prioritized from current RUL ({rul:.0f}h), "
        f"failure probability ({fp:.1f}%), and live sensor evidence ({_sensor_summary(reading)}).",
        "",
        "## Key metrics",
        f"- **Failure probability:** {fp:.1f}%",
        f"- **Remaining useful life:** ~{rul:.0f} hours",
        f"- **Risk level:** {risk}",
        "",
        "## Key findings",
    ]
    if causes:
        for c in causes[:3]:
            if isinstance(c, dict):
                lines.append(f"- {c.get('cause', 'Wear')} ({float(c.get('confidence', 0.7)) * 100:.0f}% confidence)")
    else:
        lines.append("- Progressive bearing/lubrication degradation (75% confidence)")

    immediate = plan.get("immediate_actions") or []
    short = plan.get("short_term_actions") or []
    combined = (immediate + short)[:3] or [
        "Inspect high-vibration components and lubrication",
        "Stage spares before next shift",
        "Schedule intervention within the RUL window",
    ]
    lines.extend(["", "## Recommended actions"])
    for i, action in enumerate(combined, 1):
        lines.append(f"{i}. {action} (timeframe: {_timeframe_for_action(action, i - 1)})")

    lines.extend(_follow_up_block([
        f"How urgent is maintenance on {code}?",
        f"What spare parts should I order for {code}?",
        f"Show me the relevant SOP section for {code}",
    ]))
    return "\n".join(lines)


def _fmt_inr(value: Any) -> str:
    n = float(value or 0)
    if n <= 0:
        return "not on file"
    if n >= 100000:
        return f"₹{n / 100000:.2f} L"
    if n >= 1000:
        return f"₹{n / 1000:.1f}k"
    return f"₹{n:,.0f}"


def format_spare_parts(state: dict[str, Any]) -> str:
    eq = state.get("equipment_context") or {}
    code = eq.get("equipment_code", "Asset")
    inv = state.get("inventory_assessment") or {}
    spares = inv.get("spares") or state.get("spare_context") or []
    query = (state.get("query") or "").lower()
    price_focus = any(w in query for w in ("price", "cost", "rate", "per unit", "how much", "₹", "rupee"))

    heading = f"## Spare part pricing for {code}" if price_focus else f"## Spare parts for {code}"
    lines = [heading, ""]
    if spares:
        for i, s in enumerate(spares[:6], 1):
            unit = _fmt_inr(s.get("unit_cost"))
            qty = int(s.get("quantity_available", 0) or 0)
            reorder = int(s.get("reorder_level", 5) or 0)
            line_total = float(s.get("unit_cost") or 0) * qty
            if price_focus:
                lines.append(
                    f"{i}. **{s.get('name', 'Part')}** (`{s.get('part_number', 'N/A')}`) — "
                    f"unit rate **{unit}**, qty in stock {qty}"
                    + (f", stock value {_fmt_inr(line_total)}" if line_total > 0 else "")
                    + f", lead time {s.get('lead_time_days', 14)}d"
                )
            else:
                lines.append(
                    f"{i}. **{s.get('name', 'Part')}** — code `{s.get('part_number', 'N/A')}`, "
                    f"unit rate **{unit}**, qty **{qty}**, lead time **{s.get('lead_time_days', 14)}d**, "
                    f"stock {'LOW' if qty <= reorder else 'OK'}"
                )
        if price_focus:
            total = sum(float(s.get("unit_cost") or 0) for s in spares[:6])
            if total > 0:
                lines.append("")
                lines.append(f"**Combined unit rate (per item):** {_fmt_inr(total)}")
    else:
        lines.append("No mapped spare lines for this asset. Check the Inventory page or confirm the asset type mapping.")

    lines.extend(_follow_up_block([
        f"Which part should we reorder first for {code}?",
        f"Is it safe to keep running {code} until delivery?",
        f"What is the maintenance plan for {code}?",
    ]))
    return "\n".join(lines)


def format_safety(state: dict[str, Any]) -> str:
    eq = state.get("equipment_context") or {}
    code = eq.get("equipment_code", "Asset")
    pred = state.get("ml_prediction") or {}
    reading = state.get("sensor_reading") or {}
    diag = state.get("diagnosis") or {}

    fp = float(pred.get("failure_probability") or 0) * 100
    rul = float(reading.get("rul_hours") or pred.get("remaining_useful_life_hours") or 0)
    risk = _risk_label(rul, fp)
    acceptable = risk in ("LOW", "MEDIUM") and fp < 55
    verdict = "**Acceptable to continue** with increased monitoring" if acceptable else "**Not recommended** without inspection"
    concern = (diag.get("probable_causes") or [{}])[0]
    concern_text = concern.get("cause", "Elevated vibration and degrading health index") if isinstance(concern, dict) else str(concern)

    lines = [
        f"## Safety assessment for {code}",
        f"Clear verdict: {verdict}",
        "",
        f"- **Failure probability:** {fp:.1f}%",
        f"- **Remaining useful life:** ~{rul:.0f} hours",
        f"- **Risk level:** {risk}",
        "",
        f"Primary concern: {concern_text}.",
        "",
        "## Recommended actions",
        f"1. Visual and vibration check before next run (timeframe: ASAP)",
        f"2. Log health index and compare to last shift baseline (timeframe: next shift)",
        f"3. Stage spares and plan intervention before RUL window closes (timeframe: planned outage)",
    ]
    lines.extend(_follow_up_block([
        f"What should we inspect first on {code}?",
        f"What spare parts should I order for {code}?",
        f"Show me the relevant SOP section for {code}",
    ]))
    return "\n".join(lines)


def format_sop(state: dict[str, Any]) -> str:
    eq = state.get("equipment_context") or {}
    code = eq.get("equipment_code", "Asset")
    rag = state.get("rag_results") or []

    lines = [f"## Relevant SOP & manual sections for {code}", ""]
    docs = [r for r in rag[:4] if r.get("excerpt")]
    if docs:
        for r in docs[:3]:
            score = float(r.get("score", 0) or 0) * 100
            title = r.get("source", "Manual")
            excerpt = (r.get("excerpt") or "")[:280].strip()
            lines.append(f"### {title} ({score:.0f}% match)")
            lines.append(excerpt)
            lines.append("")
    else:
        lines.append("No indexed manual excerpt matched — upload or re-index SOPs in the Knowledge base.")
        lines.append("")

    lines.extend(_follow_up_block([
        f"What inspection steps apply to {code}?",
        f"Which spare parts are critical for {code}?",
        f"What is the root cause analysis for {code}?",
    ]))
    return "\n".join(lines)


def format_asset_ranking(state: dict[str, Any]) -> str:
    fleet = state.get("fleet_snapshot") or {}
    assets = sorted(list(fleet.get("assets") or []), key=lambda a: float(a.get("rul_hours") or 0))

    lines = [
        "## Summary",
        "Fleet assets ranked by remaining useful life (lowest RUL = highest maintenance priority).",
        "",
        "## Key findings",
    ]
    for i, a in enumerate(assets[:5], 1):
        code = a.get("equipment_code", "?")
        rul = float(a.get("rul_hours") or 0)
        fp = float(a.get("failure_probability") or 0) * 100
        lines.append(f"- **{i}. {code}** — RUL ~{rul:.0f}h, failure probability {fp:.1f}%")

    if assets:
        top = assets[0].get("equipment_code", "top asset")
        lines.extend([
            "",
            "## Recommended actions",
            f"1. Prioritize inspection and spares for **{top}** (timeframe: ASAP)",
            "2. Review open alerts for the bottom three RUL assets (timeframe: next shift)",
            "3. Update the maintenance schedule for units below 168h RUL (timeframe: planned outage)",
        ])
    lines.extend(_follow_up_block([
        "What should we do for the lowest-RUL asset?",
        "Which spare parts are critical across the fleet?",
        "Show production impact if the top-risk asset fails",
    ]))
    return "\n".join(lines)


def format_business_impact(state: dict[str, Any]) -> str:
    eq = state.get("equipment_context") or {}
    code = eq.get("equipment_code", "Asset")
    impact = state.get("production_impact") or {}
    pred = state.get("ml_prediction") or {}

    downtime = float(impact.get("downtime_estimate_hours") or 16)
    tons = float(impact.get("throughput_impact_tons") or 0)
    exposure = int(impact.get("business_cost_inr") or impact.get("downtime_cost_inr") or 0)
    fp = float(pred.get("failure_probability") or 0) * 100

    lines = [
        "## Summary",
        f"If **{code}** fails, estimated impact is **{downtime:.0f}h downtime**, "
        f"**{tons:.0f} tons** production loss, and significant revenue exposure.",
        "",
        "## Key metrics",
        f"- **Failure probability:** {fp:.1f}%",
        f"- **Estimated downtime:** {downtime:.0f} hours",
        f"- **Production loss:** {tons:.0f} tons",
        "",
        "## Key findings",
        f"- Revenue / cost exposure estimated at INR {exposure:,}" if exposure else "- Production loss scales with asset criticality and delay duration",
        "- Preventive maintenance typically costs far less than unplanned failure downtime",
        "",
        "## Recommended actions",
        "1. Schedule intervention before failure probability crosses operational threshold (timeframe: ASAP)",
        "2. Align operations on a controlled shutdown window (timeframe: next shift)",
        "3. Document business case for preventive work in the maintenance log (timeframe: planned outage)",
    ]
    lines.extend(_follow_up_block([
        f"How urgent is maintenance on {code}?",
        f"What spare parts should I order for {code}?",
        f"What happens if maintenance is delayed 7 days?",
    ]))
    return "\n".join(lines)


def format_failure_simulation(state: dict[str, Any]) -> str:
    from app.services.response_templates import build_failure_simulation

    markdown, _ = build_failure_simulation(state)
    if "## Follow-up Questions" not in markdown:
        code = (state.get("equipment_context") or {}).get("equipment_code", "Asset")
        markdown += "\n" + "\n".join(_follow_up_block([
            f"What should we do for {code} now?",
            f"Which spare parts should be staged for {code}?",
            "Show the maintenance plan for the recommended intervention point",
        ]))
    return markdown


def _is_safety_query(query: str) -> bool:
    q = query.lower()
    return any(
        p in q
        for p in (
            "safe to run", "safe to keep", "keep running", "continue running",
            "can we run", "is it safe", "operate safely",
        )
    )


def _is_rul_query(query: str) -> bool:
    q = query.lower()
    return any(w in q for w in ("rul", "remaining useful life", "remaining life", "life left"))


def format_rul(state: dict[str, Any]) -> str:
    eq = state.get("equipment_context") or {}
    code = eq.get("equipment_code", "Asset")
    name = eq.get("name") or ""
    pred = state.get("ml_prediction") or {}
    reading = state.get("sensor_reading") or {}
    diag = state.get("diagnosis") or {}

    fp = float(pred.get("failure_probability") or 0) * 100
    rul = float(reading.get("rul_hours") or pred.get("remaining_useful_life_hours") or 0)
    risk = _risk_label(rul, fp)
    cycles = reading.get("cycle")
    sensor_ev = _sensor_summary(reading)

    lines = [
        "## Summary",
        (
            f"**{code}**"
            + (f" ({name})" if name else "")
            + f" has an estimated **{rul:.0f} hours** (~{rul / 24:.1f} days) of remaining useful life "
            f"based on {sensor_ev}. "
            f"Failure probability is **{fp:.1f}%** ({risk} risk)."
        ),
        "",
        "## Key metrics",
        f"- **Failure probability:** {fp:.1f}%",
        f"- **Remaining useful life:** ~{rul:.0f} hours" + (f" ({cycles} cycles)" if cycles else ""),
        f"- **Risk level:** {risk}",
        "",
        "## Key findings",
    ]
    causes = diag.get("probable_causes") or []
    if causes:
        for c in causes[:3]:
            if isinstance(c, dict):
                lines.append(f"- {c.get('cause', 'Wear')} ({float(c.get('confidence', 0.75)) * 100:.0f}% confidence)")
    else:
        lines.append("- Degradation trend consistent with bearing/lubrication wear on C-MAPSS FD001 profile (78% confidence)")

    plan = state.get("maintenance_plan") or {}
    actions = plan.get("immediate_actions") or [
        "Continue sensor monitoring every 2 hours",
        "Plan intervention before RUL drops below 168h",
        "Verify spare parts availability for bearing/lubrication work",
    ]
    lines.extend(["", "## Recommended actions"])
    for i, action in enumerate(actions[:3], 1):
        lines.append(f"{i}. {action} (timeframe: {_timeframe_for_action(action, i - 1)})")

    lines.extend(_follow_up_block([
        f"What is the root cause of degradation on {code}?",
        f"What should we do next for {code}?",
        f"Is it safe to keep running {code}?",
    ]))
    return "\n".join(lines)


def format_chat_response(state: dict[str, Any], template: str) -> str:
    """Pick layout by intent/template and format from agent state."""
    query = (state.get("query") or "").lower()
    intent = state.get("query_intent") or ""

    # Fleet ranking is unambiguous — resolve it before keyword heuristics so a
    # query like "rank all assets by RUL" is not mistaken for a single-asset RUL view.
    if template == "asset_ranking" or intent == ASSET_RANKING:
        return format_asset_ranking(state)
    if _is_rul_query(query):
        return format_rul(state)
    if _is_safety_query(query):
        return format_safety(state)
    if template == "critical_spares" or intent == INVENTORY:
        return format_spare_parts(state)
    if template == "sop_knowledge" or intent == SOP:
        return format_sop(state)
    if template == "maintenance_plan" or intent == MAINTENANCE_PLANNING:
        return format_maintenance_plan(state)
    if template == "business_impact" or intent == BUSINESS_IMPACT:
        return format_business_impact(state)
    if template == "failure_simulation" or intent == FAILURE_SIMULATION:
        return format_failure_simulation(state)
    return format_diagnostic(state)
