"""AI Maintenance Decision Simulator — delay vs act-now intelligence with scenario comparison."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependency_model import (
    _edges_from_defaults,
    aggregate_impact,
    compute_cascade,
    load_dependency_edges,
)
from app.core.fleet import PRODUCTION_RATE_TPH
from app.models import FailureScenarioRun
from app.services.agents.orchestrator import get_orchestrator
from app.services.agents.reasoning_panel import build_reasoning_panel
from app.services.business_impact_service import compute_asset_business_impact
from app.services.equipment_service import get_equipment, get_plant_priority, list_spare_parts
from app.services.live_stream import get_next_reading
from app.services.llm_service import llm_service
from app.services.ml.predictive_engine import pm_engine, risk_engine
from app.services.operational_context import load_operational_context
from app.services.scenario_service import FAILURE_MODES, _build_contingency, _estimate_downtime

RISK_ORDER = ["low", "medium", "high", "critical"]

DELAY_PRESETS = {
    "maintain_today": {"label": "Scenario A — Maintain Today", "delay_hours": 0},
    "delay_24h": {"label": "Delay 24 Hours", "delay_hours": 24},
    "delay_3d": {"label": "Scenario B — Delay 3 Days", "delay_hours": 72},
    "delay_7d": {"label": "Scenario C — Delay 7 Days", "delay_hours": 168},
}


def _risk_str(level) -> str:
    if level is None:
        return "medium"
    return level.value if hasattr(level, "value") else str(level).lower()


def _escalation_label(before: str, after: str) -> str:
    b, a = before.lower(), after.lower()
    if b == a:
        return b.upper()
    return f"{b.upper()} → {a.upper()}"


def _format_delay_label(hours: int, mode: str = "delay") -> str:
    if mode == "immediate_failure":
        return "Immediate failure (no maintenance deferral)"
    if hours <= 0:
        return "Maintain today (0-day delay)"
    if hours == 24:
        return "24 hours (1 day)"
    if hours == 72:
        return "3 days (72 hours)"
    if hours == 168:
        return "7 days (168 hours)"
    if hours % 24 == 0:
        days = hours // 24
        return f"{days} days ({hours} hours)"
    return f"{hours} hours ({hours / 24:.1f} days)"


def _degrade_reading(reading: dict, delay_hours: int, *, maintain_today: bool = False) -> dict:
    out = dict(reading)
    if maintain_today:
        out["health_indicator"] = min(95, (out.get("health_indicator") or 60) + 12)
        out["vibration"] = max(0.5, (out.get("vibration") or 2) * 0.92)
        return out
    if delay_hours <= 0:
        return out
    days = delay_hours / 24
    out["health_indicator"] = max(5, (out.get("health_indicator") or 60) - days * 7)
    out["vibration"] = min(12, (out.get("vibration") or 2) + days * 0.35)
    out["temperature"] = min(115, (out.get("temperature") or 70) + days * 1.8)
    return out


def _failure_reading(reading: dict, failure_mode: str = "bearing_failure") -> dict:
    mode = FAILURE_MODES.get(failure_mode, FAILURE_MODES["bearing_failure"])
    out = dict(reading)
    out.update({k: v for k, v in mode.items() if k != "label"})
    return out


async def _load_asset_context(db: AsyncSession, equipment_id: int) -> dict:
    equipment = await get_equipment(db, equipment_id)
    if not equipment:
        raise ValueError("Equipment not found")

    meta = equipment.metadata_json or {}
    downtime_cost = meta.get("downtime_cost", 50000)
    code = equipment.equipment_code

    baseline_reading = get_next_reading(equipment_id)
    all_spares = await list_spare_parts(db)
    spares = [
        {
            "part_number": s.part_number,
            "name": s.name,
            "quantity_available": s.quantity_available,
            "reorder_level": s.reorder_level,
            "lead_time_days": s.lead_time_days,
            "unit_cost": s.unit_cost,
            "equipment_type": s.equipment_type,
        }
        for s in all_spares
        if s.equipment_type == equipment.equipment_type
    ]
    primary_spare = spares[0] if spares else None
    bearing_stock = primary_spare["quantity_available"] if primary_spare else 0
    lead_time = primary_spare["lead_time_days"] if primary_spare else 14
    spare_name = primary_spare["name"] if primary_spare else "Critical spare"

    operational = await load_operational_context(db, equipment_id)
    priority_list = await get_plant_priority(db)
    priority_item = next((p for p in priority_list if p["equipment_id"] == equipment_id), None)
    priority_rank = next((i + 1 for i, p in enumerate(priority_list) if p["equipment_id"] == equipment_id), None)

    edges = await load_dependency_edges(db)
    if not edges:
        edges = _edges_from_defaults()

    return {
        "equipment": equipment,
        "code": code,
        "downtime_cost": downtime_cost,
        "baseline_reading": baseline_reading,
        "spares": spares,
        "primary_spare": primary_spare,
        "bearing_stock": bearing_stock,
        "lead_time_days": lead_time,
        "spare_name": spare_name,
        "operational": operational,
        "priority_item": priority_item,
        "priority_rank": priority_rank,
        "edges": edges,
    }


def _project_scenario(
    ctx: dict,
    *,
    delay_hours: int,
    immediate_failure: bool = False,
    failure_mode: str = "bearing_failure",
    scenario_id: str,
    scenario_label: str,
) -> dict:
    equipment = ctx["equipment"]
    code = ctx["code"]
    downtime_cost = ctx["downtime_cost"]
    baseline_reading = ctx["baseline_reading"]
    spares = ctx["spares"]
    primary_spare = ctx["primary_spare"]
    bearing_stock = ctx["bearing_stock"]
    lead_time = ctx["lead_time_days"]
    edges = ctx["edges"]

    baseline_pred = pm_engine.predict_rul(baseline_reading)
    baseline_rul = float(baseline_pred.get("remaining_useful_life_hours") or baseline_reading.get("rul_hours") or 48)
    baseline_fp = float(baseline_pred.get("failure_probability") or 0.3)
    baseline_risk = risk_engine.compute(
        criticality=equipment.criticality,
        failure_probability=baseline_fp,
        downtime_cost=downtime_cost,
        spare_availability=bearing_stock,
        lead_time_days=lead_time,
        rul_hours=baseline_rul,
        reorder_level=primary_spare["reorder_level"] if primary_spare else 5,
    )
    baseline_risk_level = _risk_str(baseline_risk["risk_level"])

    if immediate_failure:
        reading = _failure_reading(baseline_reading, failure_mode)
        failure_prob = 0.92
        downtime_hours = _estimate_downtime(failure_mode, bearing_stock <= 0, lead_time)
        affected = compute_cascade(code, edges, downtime_hours)
        impact = aggregate_impact(code, downtime_hours, downtime_cost, equipment.criticality, affected)
        rul_after = max(2, baseline_rul * 0.05)
    else:
        maintain = delay_hours == 0 and scenario_id == "maintain_today"
        reading = _degrade_reading(baseline_reading, delay_hours, maintain_today=maintain)
        pred = pm_engine.predict_rul(reading)
        rul_after = float(pred.get("remaining_useful_life_hours") or baseline_rul)
        failure_prob = float(pred.get("failure_probability") or baseline_fp)

        if delay_hours > 0:
            delay_factor = min(0.45, (delay_hours / 168) * 0.35)
            failure_prob = min(0.98, failure_prob + delay_factor)

        rul_days_after = rul_after / 24
        delay_days = delay_hours / 24
        failure_during_delay = delay_hours > 0 and rul_days_after < delay_days

        if failure_during_delay or (immediate_failure is False and failure_prob >= 0.75 and delay_hours >= 72):
            mode = failure_mode
            downtime_hours = _estimate_downtime(mode, bearing_stock <= 0, lead_time)
            affected = compute_cascade(code, edges, downtime_hours)
            impact = aggregate_impact(code, downtime_hours, downtime_cost, equipment.criticality, affected)
            failure_prob = min(0.98, failure_prob + 0.12)
        elif maintain:
            downtime_hours = 6.0
            affected = []
            impact = aggregate_impact(code, downtime_hours, downtime_cost, equipment.criticality, [])
            failure_prob = max(0.05, failure_prob * 0.35)
            rul_after = min(baseline_rul * 1.4, rul_after + 48)
        else:
            downtime_hours = 0.0
            affected = []
            impact = {
                "total_downtime_hours": 0,
                "total_production_loss_tons": 0,
                "total_cost_inr": int(downtime_cost * failure_prob * (equipment.criticality / 5) * 0.4),
                "direct_cost_inr": 0,
                "cascade_cost_inr": 0,
                "source_downtime_hours": 0,
                "source_production_loss_tons": 0,
                "cascade_production_loss_tons": 0,
            }

    risk = risk_engine.compute(
        criticality=equipment.criticality,
        failure_probability=failure_prob,
        downtime_cost=downtime_cost,
        spare_availability=bearing_stock,
        lead_time_days=lead_time,
        rul_hours=rul_after,
        reorder_level=primary_spare["reorder_level"] if primary_spare else 5,
    )
    risk_level = _risk_str(risk["risk_level"])

    health = reading.get("health_indicator") or 60
    bi = compute_asset_business_impact(
        downtime_cost_per_day=downtime_cost,
        criticality=equipment.criticality,
        health_score=health,
        rul_hours=rul_after,
        failure_probability=failure_prob,
    )

    if immediate_failure or downtime_hours > 8:
        downtime_cost_inr = impact["total_cost_inr"]
        avoided_loss_inr = bi["avoided_loss_inr"]
    else:
        downtime_cost_inr = bi["downtime_cost_inr"]
        avoided_loss_inr = bi["avoided_loss_inr"]

    maintenance_cost_inr = bi["maintenance_cost_inr"]
    production_tons = impact.get("total_production_loss_tons", 0)

    return {
        "id": scenario_id,
        "label": scenario_label,
        "delay_hours": delay_hours,
        "immediate_failure": immediate_failure,
        "failure_probability_pct": round(failure_prob * 100),
        "baseline_failure_probability_pct": round(baseline_fp * 100),
        "rul_hours": round(rul_after, 1),
        "rul_days": round(rul_after / 24, 1),
        "baseline_rul_hours": round(baseline_rul, 1),
        "baseline_rul_days": round(baseline_rul / 24, 1),
        "risk_level": risk_level,
        "baseline_risk_level": baseline_risk_level,
        "risk_escalation": _escalation_label(baseline_risk_level, risk_level),
        "risk_escalated": risk.get("escalated", False),
        "escalation_reason": risk.get("escalation_reason"),
        "downtime_hours": round(downtime_hours, 1),
        "production_loss_tons": round(production_tons, 1),
        "downtime_cost_inr": downtime_cost_inr,
        "maintenance_cost_inr": maintenance_cost_inr,
        "avoided_loss_inr": avoided_loss_inr,
        "net_exposure_inr": max(0, downtime_cost_inr - avoided_loss_inr + maintenance_cost_inr),
        "affected_assets": affected if immediate_failure or downtime_hours > 8 else [],
        "affected_asset_codes": [a["equipment_code"] for a in (affected if immediate_failure or downtime_hours > 8 else [])],
        "procurement_risk": risk.get("procurement_risk", "low"),
        "anomaly_detected": pm_engine.detect_anomaly(reading).get("is_anomaly", False),
        "total_score": round(failure_prob * 100 + downtime_cost_inr / 10000 + (RISK_ORDER.index(risk_level) if risk_level in RISK_ORDER else 2) * 15, 2),
    }


def _build_recommendation(ctx: dict, scenarios: list[dict], best: dict, selected: dict) -> dict:
    code = ctx["code"]
    primary = ctx["primary_spare"]
    spare_name = ctx["spare_name"]
    lead_time = ctx["lead_time_days"]
    bearing_stock = ctx["bearing_stock"]
    baseline_rul_days = scenarios[0]["baseline_rul_days"] if scenarios else 0
    selected_label = selected.get("label") or _format_delay_label(int(selected.get("delay_hours") or 0))

    if best["id"] == "maintain_today":
        action = f"Perform Planned Maintenance on {code} Today"
        reason = (
            f"Maintaining today reduces failure probability to {best['failure_probability_pct']}% "
            f"with ₹{(best['avoided_loss_inr'] / 100000):.1f}L avoided loss vs "
            f"{selected_label.lower()}."
        )
    elif bearing_stock <= 0 and lead_time > baseline_rul_days:
        action = f"Replace {spare_name} Immediately"
        reason = f"Lead time ({lead_time} days) exceeds RUL ({baseline_rul_days:.1f} days) with zero stock."
    elif best["immediate_failure"]:
        action = "Activate Emergency Response — Do Not Delay"
        reason = "Immediate failure projects maximum cascade impact across downstream assets."
    else:
        action = f"Schedule Maintenance Within {max(24, int(best['delay_hours']))} Hours"
        reason = best.get("escalation_reason") or f"Selected delay keeps net exposure lowest at ₹{best['net_exposure_inr']:,}."

    confidence = 0.92 if bearing_stock <= 0 and lead_time > baseline_rul_days else 0.85
    if ctx["priority_item"] and ctx["priority_item"].get("priority_score", 0) > 80:
        confidence = min(0.97, confidence + 0.05)

    return {
        "action": action,
        "reason": reason,
        "confidence_pct": round(confidence * 100),
        "best_scenario_id": best["id"],
        "best_scenario_label": best["label"],
    }


def _build_reasoning_chain(
    ctx: dict, baseline: dict, selected: dict, recommendation: dict, *, delay_label: str
) -> list[dict]:
    priority = ctx["priority_item"]
    operational = ctx["operational"]
    rank = ctx.get("priority_rank")
    return [
        {
            "step": "Scenario Selected",
            "detail": (
                f"Simulated maintenance decision: {delay_label}. "
                f"Projected failure probability {baseline['failure_probability_pct']}% → "
                f"{selected['failure_probability_pct']}% after deferral."
            ),
        },
        {
            "step": "RUL Prediction",
            "detail": (
                f"XGBoost baseline RUL {baseline['rul_days']:.1f} days ({baseline['rul_hours']:.0f}h). "
                f"After {delay_label.lower()}: {selected['rul_days']:.1f} days — failure probability "
                f"{baseline['failure_probability_pct']}% → {selected['failure_probability_pct']}%."
            ),
        },
        {
            "step": "Inventory Constraint",
            "detail": (
                f"{ctx['spare_name']}: stock {ctx['bearing_stock']}, lead time {ctx['lead_time_days']} days. "
                f"Procurement risk: {selected.get('procurement_risk', 'low').upper()}."
            ),
        },
        {
            "step": "Criticality Score",
            "detail": (
                f"Asset {ctx['code']} criticality {ctx['equipment'].criticality}/5. "
                f"Priority rank #{rank or '—'} "
                f"(score {priority['priority_score'] if priority else '—'})."
            ),
        },
        {
            "step": "Operational Context",
            "detail": (
                f"{len(operational.get('open_alerts', []))} open alerts, "
                f"{len(operational.get('delay_logs', []))} recent delay logs, "
                f"{len(operational.get('maintenance_records', []))} maintenance records in context."
            ),
        },
        {
            "step": "Risk Escalation",
            "detail": (
                f"Risk path: {selected['risk_escalation']}. "
                f"{selected.get('escalation_reason') or 'Within acceptable maintenance window.'}"
            ),
        },
        {
            "step": "Final Decision",
            "detail": f"{recommendation['action']}. {recommendation['reason']}",
        },
    ]


async def run_decision_simulation(
    db: AsyncSession,
    equipment_id: int,
    *,
    mode: str = "delay",
    delay_hours: int = 72,
    custom_delay_hours: int | None = None,
    failure_mode: str = "bearing_failure",
    user_id: int | None = None,
) -> dict:
    ctx = await _load_asset_context(db, equipment_id)
    equipment = ctx["equipment"]
    code = ctx["code"]

    effective_delay = custom_delay_hours if custom_delay_hours is not None else delay_hours
    immediate = mode == "immediate_failure"

    comparison_ids = [
        ("maintain_today", DELAY_PRESETS["maintain_today"]["label"], 0, False),
        ("delay_3d", DELAY_PRESETS["delay_3d"]["label"], 72, False),
        ("delay_7d", DELAY_PRESETS["delay_7d"]["label"], 168, False),
    ]

    scenarios: list[dict] = []
    for sid, label, dh, imm in comparison_ids:
        scenarios.append(
            _project_scenario(
                ctx, delay_hours=dh, immediate_failure=imm, failure_mode=failure_mode, scenario_id=sid, scenario_label=label
            )
        )

    if immediate:
        selected = _project_scenario(
            ctx,
            delay_hours=0,
            immediate_failure=True,
            failure_mode=failure_mode,
            scenario_id="immediate_failure",
            scenario_label="Simulate Immediate Failure",
        )
    elif effective_delay == 24:
        selected = _project_scenario(
            ctx, delay_hours=24, failure_mode=failure_mode, scenario_id="delay_24h", scenario_label="Delay 24 Hours"
        )
    elif effective_delay == 72:
        selected = next(s for s in scenarios if s["id"] == "delay_3d")
        selected = dict(selected)
    elif effective_delay == 168:
        selected = next(s for s in scenarios if s["id"] == "delay_7d")
        selected = dict(selected)
    else:
        selected = _project_scenario(
            ctx,
            delay_hours=effective_delay,
            failure_mode=failure_mode,
            scenario_id="custom_delay",
            scenario_label=f"Delay {effective_delay} Hours",
        )

    best = min(scenarios, key=lambda s: s["net_exposure_inr"])
    for s in scenarios:
        s["is_best"] = s["id"] == best["id"]

    comparison = list(scenarios)
    if selected.get("id") not in {s["id"] for s in comparison}:
        comparison.append({**selected, "is_best": selected.get("id") == best["id"]})

    baseline_pred = pm_engine.predict_rul(ctx["baseline_reading"])
    baseline_rul = float(baseline_pred.get("remaining_useful_life_hours") or 48)
    baseline_fp = float(baseline_pred.get("failure_probability") or 0.3)
    baseline_risk = risk_engine.compute(
        criticality=equipment.criticality,
        failure_probability=baseline_fp,
        downtime_cost=ctx["downtime_cost"],
        spare_availability=ctx["bearing_stock"],
        lead_time_days=ctx["lead_time_days"],
        rul_hours=baseline_rul,
    )

    current_state = {
        "failure_probability_pct": round(baseline_fp * 100),
        "rul_hours": round(baseline_rul, 1),
        "rul_days": round(baseline_rul / 24, 1),
        "risk_level": _risk_str(baseline_risk["risk_level"]),
        "anomaly_detected": pm_engine.detect_anomaly(ctx["baseline_reading"]).get("is_anomaly", False),
        "health_score": round(ctx["baseline_reading"].get("health_indicator") or 60, 1),
    }

    recommendation = _build_recommendation(ctx, scenarios, best, selected)
    delay_label = _format_delay_label(effective_delay, mode)
    reasoning_chain = _build_reasoning_chain(ctx, current_state, selected, recommendation, delay_label=delay_label)

    scenario_context = {
        "decision_mode": mode,
        "delay_hours": effective_delay,
        "downtime_hours": selected["downtime_hours"],
        "affected_assets": selected["affected_assets"],
        "impact_summary": {
            "total_cost_inr": selected["downtime_cost_inr"],
            "total_production_loss_tons": selected["production_loss_tons"],
        },
        "spare_status": "critical" if ctx["bearing_stock"] <= 0 else "available",
    }

    query = (
        f"Maintenance decision for {code}: {recommendation['action']}. "
        f"Delay {effective_delay}h vs maintain today. Failure prob {selected['failure_probability_pct']}%, "
        f"RUL {selected['rul_days']}d, risk {selected['risk_escalation']}."
    )
    orch = await get_orchestrator().run(
        query=query,
        query_intent="scenario",
        page_context="AI Maintenance Decision Simulator",
        equipment_context={
            "id": equipment.id,
            "equipment_code": code,
            "name": equipment.name,
            "criticality": equipment.criticality,
            "location": equipment.location,
            "downtime_cost": ctx["downtime_cost"],
        },
        sensor_reading=ctx["baseline_reading"],
        spare_context=ctx["spares"],
        scenario_context=scenario_context,
        operational_context=ctx["operational"],
    )

    structured = orch.get("structured_output") or {}
    maintenance_plan = structured.get("maintenance_plan") or {}
    planner_actions = maintenance_plan.get("immediate_actions") or []
    if planner_actions and recommendation["action"] not in planner_actions[0]:
        recommendation["planner_actions"] = planner_actions[:4]

    reasoning_panel = orch.get("reasoning_panel") or build_reasoning_panel(
        agent_thoughts=orch.get("agent_thoughts", []),
        agent_trace=orch.get("agent_trace", []),
        citations=orch.get("citations", []),
        query_intent="scenario",
        llm_provider=llm_service.last_provider,
        structured_output=structured,
    ).model_dump()

    downstream_names = selected["affected_asset_codes"] or []
    priority = ctx["priority_item"]
    rank = ctx.get("priority_rank")

    result = {
        "simulator_type": "decision",
        "equipment_id": equipment.id,
        "equipment_code": code,
        "equipment_name": equipment.name,
        "location": equipment.location,
        "criticality": equipment.criticality,
        "mode": mode,
        "selected_delay_hours": effective_delay,
        "selected_delay_label": delay_label,
        "selected_scenario_id": selected.get("id"),
        "current_state": current_state,
        "selected_scenario": selected,
        "after_delay": {
            "failure_probability_pct": selected["failure_probability_pct"],
            "rul_days": selected["rul_days"],
            "rul_hours": selected["rul_hours"],
            "risk_level": selected["risk_level"],
            "risk_escalation": selected["risk_escalation"],
        },
        "comparison": comparison,
        "best_scenario_id": best["id"],
        "spare_availability": {
            "bearing_stock": ctx["bearing_stock"],
            "part_name": ctx["spare_name"],
            "part_number": ctx["primary_spare"]["part_number"] if ctx["primary_spare"] else None,
            "lead_time_days": ctx["lead_time_days"],
            "procurement_risk": selected["procurement_risk"],
            "status": "critical" if ctx["bearing_stock"] <= 0 else ("low" if ctx["bearing_stock"] <= (ctx["primary_spare"] or {}).get("reorder_level", 5) else "available"),
            "parts": ctx["spares"][:6],
        },
        "downstream_impact": {
            "affected_assets": downstream_names,
            "affected_details": selected["affected_assets"],
            "production_loss_tons": selected["production_loss_tons"],
        },
        "financial_impact": {
            "downtime_cost_inr": selected["downtime_cost_inr"],
            "maintenance_cost_inr": selected["maintenance_cost_inr"],
            "avoided_loss_inr": selected["avoided_loss_inr"],
            "net_exposure_inr": selected["net_exposure_inr"],
        },
        "recommendation": recommendation,
        "reasoning_chain": reasoning_chain,
        "inputs_snapshot": {
            "priority_rank": rank,
            "priority_score": priority["priority_score"] if priority else None,
            "open_alerts": len(ctx["operational"].get("open_alerts", [])),
            "delay_log_count": len(ctx["operational"].get("delay_logs", [])),
            "failure_history_count": len(ctx["operational"].get("failure_history", [])),
            "maintenance_record_count": len(ctx["operational"].get("maintenance_records", [])),
            "isolation_forest_anomaly": current_state["anomaly_detected"],
        },
        "maintenance_recommendation": {
            "immediate_actions": planner_actions or [recommendation["action"]],
            "short_term_actions": maintenance_plan.get("short_term_actions", []),
            "long_term_actions": maintenance_plan.get("long_term_actions", []),
            "monitoring_plan": maintenance_plan.get("monitoring_plan"),
            "ai_summary": orch.get("message", "")[:1200],
        },
        "contingency_plan": _build_contingency(
            code,
            failure_mode,
            selected["affected_assets"],
            selected["downtime_hours"],
            ctx["bearing_stock"] <= 0,
        ),
        "reasoning_panel": reasoning_panel,
        "agent_trace": orch.get("agent_trace", []),
        "llm_provider": llm_service.last_provider,
        "production_rate_tph": PRODUCTION_RATE_TPH.get(code, 0),
    }

    run = FailureScenarioRun(
        equipment_id=equipment.id,
        user_id=user_id,
        failure_mode=f"decision:{mode}:{effective_delay}h",
        assume_no_spare=ctx["bearing_stock"] <= 0,
        defer_maintenance_days=int(effective_delay / 24),
        result_json=result,
    )
    db.add(run)
    await db.flush()
    result["scenario_run_id"] = run.id
    return result
