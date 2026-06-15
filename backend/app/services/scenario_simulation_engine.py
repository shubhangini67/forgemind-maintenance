"""Failure scenario simulator — projects future asset state from delays, sensor shifts, and spare constraints."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.core.dependency_model import aggregate_impact, compute_cascade
from app.services.business_impact_service import compute_asset_business_impact
from app.services.ml.predictive_engine import pm_engine, risk_engine

DEFAULT_DELAY_DAYS = [1, 3, 7, 14]
SHIFT_HOURS = 8


def format_inr_compact(amount: int | float) -> str:
    """Compact INR for scenario tables (₹0, ₹20k, ₹250k, ₹4.2 Lakhs)."""
    n = int(amount or 0)
    if n == 0:
        return "₹0"
    if n >= 100_000:
        lakhs = n / 100_000
        if abs(lakhs - round(lakhs)) < 0.05:
            return f"₹{int(round(lakhs))} Lakhs"
        return f"₹{lakhs:.1f} Lakhs"
    if n >= 1_000:
        return f"₹{round(n / 1_000)}k"
    return f"₹{n:,}"


def _horizon_label(delay_hours: float) -> str:
    if delay_hours <= 0:
        return "Current"
    if delay_hours >= 24 and delay_hours % 24 == 0:
        days = int(delay_hours / 24)
        return f"+{days} Day" if days == 1 else f"+{days} Days"
    return f"+{delay_hours:.0f}h"


def _deferral_downtime_cost(delay_hours: float, failure_probability: float, downtime_cost_per_day: float) -> int:
    """Incremental downtime cost from deferring maintenance."""
    if delay_hours <= 0:
        return 0
    days = delay_hours / 24
    return int(days * downtime_cost_per_day * (0.08 + failure_probability * 0.35))


@dataclass
class ScenarioParams:
    scenario_type: str = "delay"
    delay_days: list[int] = field(default_factory=lambda: list(DEFAULT_DELAY_DAYS))
    primary_delay_hours: int | None = None
    vibration_pct_increase: float | None = None
    temperature_c: float | None = None
    spare_unavailable: bool = False
    extra_shift_hours: float | None = None


def parse_scenario_params(query: str) -> ScenarioParams | None:
    """Extract simulation parameters from natural-language what-if queries."""
    q = query.lower()
    scenario_triggers = (
        "what happens if", "what if", "happens if", "simulate", "scenario",
        "delay", "postpone", "defer", "wait", "another shift", "spare",
        "unavailable", "vibration", "temperature", "increases", "reach",
    )
    if not any(t in q for t in scenario_triggers):
        return None

    params = ScenarioParams()

    if any(w in q for w in ("spare", "unavailable", "out of stock", "no stock")):
        params.scenario_type = "spare_shortage"
        params.spare_unavailable = True

    if "another shift" in q or "one more shift" in q or "extra shift" in q:
        params.scenario_type = "shift_extension"
        params.extra_shift_hours = SHIFT_HOURS
        params.primary_delay_hours = SHIFT_HOURS

    m = re.search(r"vibration\s*(?:increases?|rise|up)\s*(?:by\s*)?(\d+)\s*%", q)
    if m:
        params.scenario_type = "sensor_degradation"
        params.vibration_pct_increase = float(m.group(1))
    elif "vibration" in q and ("increase" in q or "rise" in q or "20%" in q):
        params.scenario_type = "sensor_degradation"
        params.vibration_pct_increase = 20.0

    m = re.search(r"temperature\s*(?:reaches?|at|to)\s*(\d+)\s*°?c", q)
    if m:
        params.scenario_type = "sensor_degradation"
        params.temperature_c = float(m.group(1))
    elif "100" in q and ("temp" in q or "temperature" in q or "°c" in q):
        params.scenario_type = "sensor_degradation"
        params.temperature_c = 100.0

    delay_days: list[int] = []
    for m in re.finditer(r"(\d+)\s*(?:day|days|d)\b", q):
        d = int(m.group(1))
        if 0 < d <= 30:
            delay_days.append(d)
    if delay_days:
        params.delay_days = sorted(set(delay_days) | set(DEFAULT_DELAY_DAYS))
        params.scenario_type = "delay" if params.scenario_type == "delay" else params.scenario_type
        params.primary_delay_hours = max(delay_days) * 24
    elif "7 day" in q or "7-day" in q or "week" in q:
        params.delay_days = [1, 3, 7, 14]
        params.primary_delay_hours = 168
    elif "3 day" in q or "3-day" in q:
        params.delay_days = [1, 3, 7]
        params.primary_delay_hours = 72
    elif "24 hour" in q or "1 day" in q:
        params.delay_days = [1, 3, 7]
        params.primary_delay_hours = 24
    elif any(w in q for w in ("delay", "postpone", "defer", "wait")):
        params.delay_days = list(DEFAULT_DELAY_DAYS)
        params.primary_delay_hours = 168

    if params.extra_shift_hours and not params.delay_days:
        params.delay_days = [0, 1]

    return params


def _apply_sensor_overrides(reading: dict, params: ScenarioParams) -> dict:
    out = dict(reading)
    if params.vibration_pct_increase:
        vib = float(out.get("vibration") or 3)
        out["vibration"] = min(12, vib * (1 + params.vibration_pct_increase / 100))
    if params.temperature_c:
        out["temperature"] = float(params.temperature_c)
    return out


def _degrade_for_delay(reading: dict, delay_hours: float) -> dict:
    out = dict(reading)
    if delay_hours <= 0:
        return out
    days = delay_hours / 24
    out["health_indicator"] = max(5, float(out.get("health_indicator") or 60) - days * 7)
    out["vibration"] = min(12, float(out.get("vibration") or 2) + days * 0.35)
    out["temperature"] = min(115, float(out.get("temperature") or 70) + days * 1.8)
    return out


def _project_point(
    *,
    baseline_reading: dict,
    baseline_pred: dict,
    delay_hours: float,
    equipment_context: dict,
    spare_stock: int,
    lead_time_days: int,
    reorder_level: int,
    params: ScenarioParams,
    edges: list | None = None,
) -> dict[str, Any]:
    code = equipment_context.get("equipment_code", "Asset")
    criticality = int(equipment_context.get("criticality", 3))
    downtime_cost = float(equipment_context.get("downtime_cost") or 50000)

    if params.spare_unavailable:
        spare_stock = 0

    reading = _apply_sensor_overrides(baseline_reading, params)
    reading = _degrade_for_delay(reading, delay_hours)
    if params.extra_shift_hours and delay_hours == 0:
        reading = _degrade_for_delay(reading, params.extra_shift_hours)

    pred = pm_engine.predict_rul(reading)
    rul = float(pred.get("remaining_useful_life_hours") or baseline_pred.get("remaining_useful_life_hours") or 999)
    fp = float(pred.get("failure_probability") or 0.3)

    if delay_hours > 0:
        fp = min(0.98, fp + min(0.45, (delay_hours / 168) * 0.35))

    baseline_fp = float(baseline_pred.get("failure_probability") or 0.3)
    baseline_rul = float(baseline_pred.get("remaining_useful_life_hours") or rul)

    risk = risk_engine.compute(
        criticality=criticality,
        failure_probability=fp,
        downtime_cost=downtime_cost,
        spare_availability=spare_stock,
        lead_time_days=lead_time_days,
        rul_hours=rul,
        reorder_level=reorder_level,
    )
    rl = risk.get("risk_level")
    risk_level = rl.value if hasattr(rl, "value") else str(rl)

    health = float(reading.get("health_indicator") or 60)
    bi = compute_asset_business_impact(
        downtime_cost_per_day=downtime_cost,
        criticality=criticality,
        health_score=health,
        rul_hours=rul,
        failure_probability=fp,
    )

    downtime_h = float(bi.get("expected_downtime_hours") or 8)
    if delay_hours >= 168 and fp > 0.55:
        downtime_h = max(downtime_h, 12 + (fp - 0.5) * 20)

    production_loss_tons = round((downtime_h / 24) * {1: 400, 2: 600, 3: 800, 4: 1000, 5: 1200}.get(criticality, 800), 1)

    downtime_cost_inr = _deferral_downtime_cost(delay_hours, fp, downtime_cost)

    return {
        "label": _horizon_label(delay_hours),
        "delay_hours": delay_hours,
        "delay_days": round(delay_hours / 24, 1),
        "rul_hours": round(rul, 1),
        "failure_probability_pct": round(fp * 100, 1),
        "risk_level": risk_level,
        "health_score": round(health, 1),
        "rul_delta_hours": round(rul - baseline_rul, 1),
        "failure_probability_delta_pct": round((fp - baseline_fp) * 100, 1),
        "risk_delta": risk_level,
        "downtime_estimate_hours": round(downtime_h, 1),
        "production_loss_tons": production_loss_tons,
        "downtime_cost_inr": downtime_cost_inr,
        "business_cost_inr": int(bi.get("downtime_cost_inr") or 0),
        "preventive_maintenance_cost_inr": int(bi.get("maintenance_cost_inr") or 40000),
        "potential_savings_inr": int(bi.get("avoided_loss_inr") or 0),
        "operational_impact": (
            f"{production_loss_tons}t at risk · {format_inr_compact(downtime_cost_inr)} deferral exposure"
        ),
    }


def build_simulation_markdown(
    sim: dict[str, Any],
    *,
    equipment_code: str = "Asset",
    equipment_name: str = "",
    query: str = "",
) -> str:
    """Render failure-simulation output as a decision-support markdown table."""
    cs = sim.get("current_state") or {}
    projections = sim.get("projections") or []
    bi = sim.get("business_impact") or {}
    rec = sim.get("recommended_action") or "Maintain current maintenance schedule."

    risk_title = str(cs.get("risk_level") or "medium").replace("_", " ").title()
    lines = [
        "## Failure Scenario Simulation",
        "",
        f"**Asset:** {equipment_code}" + (f" — {equipment_name}" if equipment_name else ""),
    ]
    if query:
        lines.append(f"**Query:** {query}")
    lines.extend([
        "",
        "| Scenario | RUL | Failure Probability | Risk | Downtime Cost |",
        "|-----------|-----|---------------------|------|---------------|",
        (
            f"| Current | {cs.get('rul_hours', '—')}h | {cs.get('failure_probability_pct', '—')}% "
            f"| {risk_title} | ₹0 |"
        ),
    ])
    for p in projections:
        if p.get("label") == "Current":
            continue
        rl = str(p.get("risk_level") or "medium").replace("_", " ").title()
        lines.append(
            f"| {p.get('label')} | {p.get('rul_hours')}h | {p.get('failure_probability_pct')}% "
            f"| {rl} | {format_inr_compact(p.get('downtime_cost_inr', 0))} |"
        )

    lines.extend([
        "",
        "### Business Impact Summary",
        f"- **Additional failure risk:** +{bi.get('additional_failure_risk_pct', 0)}%",
        f"- **Potential downtime:** {bi.get('estimated_downtime_hours', '—')}h",
        f"- **Estimated production loss:** {bi.get('estimated_production_loss_tons', '—')} tons",
        f"- **Deferral exposure (selected horizon):** {format_inr_compact(bi.get('estimated_repair_cost_inr', 0))}",
        f"- **Preventive maintenance cost:** {format_inr_compact(bi.get('preventive_maintenance_cost_inr', 40000))}",
        f"- **Potential savings from early action:** {format_inr_compact(bi.get('potential_savings_inr', 0))}",
        "",
        "### Recommended Action",
        "",
        rec,
    ])
    return "\n".join(lines)


def run_scenario_simulation(
    *,
    query: str,
    equipment_context: dict,
    sensor_reading: dict,
    spare_context: list,
    operational_context: dict | None = None,
    dependency_edges: list | None = None,
    force_standard_horizons: bool = False,
) -> dict[str, Any]:
    """Run multi-horizon scenario simulation from live asset context."""
    if force_standard_horizons:
        params = ScenarioParams(delay_days=list(DEFAULT_DELAY_DAYS), primary_delay_hours=168)
    else:
        params = parse_scenario_params(query) or ScenarioParams(delay_days=list(DEFAULT_DELAY_DAYS))

    profile_stock = min((s.get("quantity_available", 0) for s in spare_context), default=0)
    lead_time = max((s.get("lead_time_days", 14) for s in spare_context), default=14)
    reorder = min((s.get("reorder_level", 5) for s in spare_context), default=5)
    if params.spare_unavailable:
        profile_stock = 0

    baseline_reading = dict(sensor_reading or {})
    baseline_pred = pm_engine.predict_rul(baseline_reading)
    baseline_fp = float(baseline_pred.get("failure_probability") or 0.3)
    baseline_rul = float(baseline_pred.get("remaining_useful_life_hours") or 999)

    criticality = int(equipment_context.get("criticality", 3))
    baseline_risk = risk_engine.compute(
        criticality=criticality,
        failure_probability=baseline_fp,
        downtime_cost=float(equipment_context.get("downtime_cost") or 50000),
        spare_availability=profile_stock,
        lead_time_days=lead_time,
        rul_hours=baseline_rul,
        reorder_level=reorder,
        delay_log_count=len((operational_context or {}).get("delay_logs") or []),
    )
    brl = baseline_risk.get("risk_level")
    baseline_risk_level = brl.value if hasattr(brl, "value") else str(brl)

    current_state = {
        "rul_hours": round(baseline_rul, 1),
        "failure_probability_pct": round(baseline_fp * 100, 1),
        "health_score": round(float(baseline_reading.get("health_indicator") or 60), 1),
        "risk_level": baseline_risk_level,
        "risk_score_100": baseline_risk.get("score_breakdown", {}).get("final_score_100"),
        "spare_stock": profile_stock,
        "lead_time_days": lead_time,
    }

    projections: list[dict] = []
    horizons = [d * 24 for d in params.delay_days]
    if params.extra_shift_hours:
        horizons = [0, params.extra_shift_hours] + horizons
    if params.primary_delay_hours and params.primary_delay_hours not in horizons:
        horizons.append(params.primary_delay_hours)
    horizons = sorted(set(h for h in horizons if h >= 0))[:6]

    for h in horizons:
        pt = _project_point(
            baseline_reading=baseline_reading,
            baseline_pred=baseline_pred,
            delay_hours=h,
            equipment_context=equipment_context,
            spare_stock=profile_stock,
            lead_time_days=lead_time,
            reorder_level=reorder,
            params=params,
            edges=dependency_edges,
        )
        projections.append(pt)

    primary = projections[-1] if projections else current_state
    max_delay_proj = max(projections, key=lambda p: p.get("failure_probability_pct", 0)) if projections else primary

    recommendation = "Maintain on current schedule."
    if max_delay_proj.get("failure_probability_pct", 0) >= 75:
        recommendation = "Do not delay — failure probability exceeds 75%. Schedule intervention immediately."
    elif any(p.get("delay_days", 0) >= 7 for p in projections) and max_delay_proj.get("failure_probability_delta_pct", 0) >= 15:
        recommendation = "Do not delay beyond 7 days — failure probability rise exceeds safe threshold."
    elif params.spare_unavailable:
        recommendation = "Procure critical spares before deferring maintenance — zero stock with active degradation."
    elif params.temperature_c and params.temperature_c >= 100:
        recommendation = "Temperature at 100°C exceeds alarm band — reduce load and inspect lubrication within 24h."

    primary_delay = params.primary_delay_hours or (projections[-1]["delay_hours"] if projections else 0)
    selected = next((p for p in projections if p["delay_hours"] == primary_delay), projections[-1] if projections else {})

    business_impact = {
        "scenario_label": selected.get("label", "Selected horizon"),
        "additional_failure_risk_pct": selected.get("failure_probability_delta_pct", 0),
        "estimated_downtime_hours": selected.get("downtime_estimate_hours", 0),
        "estimated_production_loss_tons": selected.get("production_loss_tons", 0),
        "estimated_repair_cost_inr": selected.get("downtime_cost_inr", 0),
        "preventive_maintenance_cost_inr": selected.get("preventive_maintenance_cost_inr", 40000),
        "potential_savings_inr": max(
            0,
            int(selected.get("potential_savings_inr", 0) or 0)
            - int(selected.get("preventive_maintenance_cost_inr", 0) or 0),
        ),
    }

    return {
        "scenario_type": params.scenario_type,
        "params": {
            "delay_days": params.delay_days,
            "vibration_pct_increase": params.vibration_pct_increase,
            "temperature_c": params.temperature_c,
            "spare_unavailable": params.spare_unavailable,
            "extra_shift_hours": params.extra_shift_hours,
        },
        "current_state": current_state,
        "projections": projections,
        "risk_delta": selected.get("failure_probability_delta_pct", 0),
        "rul_delta_hours": selected.get("rul_delta_hours", 0),
        "recommended_action": recommendation,
        "business_impact": business_impact,
        "operational_impact": selected.get("operational_impact", ""),
        "markdown_table": build_simulation_markdown(
            {
                "current_state": current_state,
                "projections": projections,
                "business_impact": business_impact,
                "recommended_action": recommendation,
            },
            equipment_code=equipment_context.get("equipment_code", "Asset"),
            equipment_name=equipment_context.get("name", ""),
            query=query,
        ),
    }
