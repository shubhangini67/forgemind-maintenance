"""Failure scenario simulator — operational decision support with dependency cascade."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependency_model import (
    _edges_from_defaults,
    aggregate_impact,
    compute_cascade,
    get_dependency_graph,
    load_dependency_edges,
)
from app.core.fleet import CANONICAL_FLEET, PRODUCTION_RATE_TPH
from app.models import FailureScenarioRun
from app.services.agents.orchestrator import get_orchestrator
from app.services.agents.reasoning_panel import build_reasoning_panel
from app.services.equipment_service import get_equipment, list_spare_parts
from app.services.live_stream import get_next_reading
from app.services.llm_service import llm_service
from app.services.ml.predictive_engine import pm_engine, risk_engine

FAILURE_MODES = {
    "bearing_failure": {"vibration": 9.5, "temperature": 95, "health_indicator": 35, "label": "Bearing failure"},
    "motor_overheat": {"temperature": 110, "motor_current": 85, "health_indicator": 40, "label": "Motor overheat"},
    "pump_seizure": {"vibration": 8.0, "pressure": 0.5, "motor_current": 90, "label": "Pump seizure"},
    "unplanned_shutdown": {"health_indicator": 10, "vibration": 10, "temperature": 100, "label": "Unplanned shutdown"},
}


async def get_scenario_dependencies(db: AsyncSession) -> dict:
    return await get_dependency_graph(db)


async def simulate_failure(
    db: AsyncSession,
    equipment_id: int,
    failure_mode: str = "bearing_failure",
    defer_maintenance_days: int = 0,
    assume_no_spare: bool = False,
    user_id: int | None = None,
) -> dict:
    equipment = await get_equipment(db, equipment_id)
    if not equipment:
        raise ValueError("Equipment not found")

    meta = equipment.metadata_json or {}
    downtime_cost = meta.get("downtime_cost", 50000)
    code = equipment.equipment_code

    # --- Baseline vs scenario ML ---
    baseline_reading = get_next_reading(equipment_id)
    baseline_pred = pm_engine.predict_rul(baseline_reading)
    baseline_rul = float(baseline_pred.get("remaining_useful_life_hours") or baseline_reading.get("rul_hours") or 48)

    mode = FAILURE_MODES.get(failure_mode, FAILURE_MODES["bearing_failure"])
    scenario_reading = dict(baseline_reading)
    scenario_reading.update({k: v for k, v in mode.items() if k != "label"})
    if defer_maintenance_days > 0:
        scenario_reading["health_indicator"] = max(
            5, (scenario_reading.get("health_indicator") or 50) - defer_maintenance_days * 8
        )

    scenario_pred = pm_engine.predict_rul(scenario_reading)
    scenario_rul = float(scenario_pred.get("remaining_useful_life_hours") or 4)
    anomaly = pm_engine.detect_anomaly(scenario_reading)
    failure_prob = float(scenario_pred.get("failure_probability") or 0.85)

    # --- Spare availability (real inventory) ---
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
    low_stock = [s for s in spares if s["quantity_available"] <= s["reorder_level"]]
    primary_spare = spares[0] if spares else None
    lead_time = (primary_spare["lead_time_days"] if primary_spare else 14) + (48 // 24 if assume_no_spare else 0)
    spare_status = "critical" if assume_no_spare or not spares else ("low" if low_stock else "available")

    downtime_hours = _estimate_downtime(failure_mode, assume_no_spare, lead_time)

    # --- Dependency cascade ---
    edges = await load_dependency_edges(db)
    if not edges:
        edges = _edges_from_defaults()
    affected_assets = compute_cascade(code, edges, downtime_hours)
    impact = aggregate_impact(code, downtime_hours, downtime_cost, equipment.criticality, affected_assets)

    equipment_context = {
        "id": equipment.id,
        "equipment_code": code,
        "name": equipment.name,
        "equipment_type": equipment.equipment_type,
        "criticality": equipment.criticality,
        "location": equipment.location,
        "downtime_cost": downtime_cost,
    }

    risk = risk_engine.compute(
        criticality=equipment.criticality,
        failure_probability=failure_prob,
        downtime_cost=downtime_cost,
        spare_availability=primary_spare["quantity_available"] if primary_spare else 0,
        lead_time_days=lead_time,
    )
    risk_level = risk["risk_level"]
    if hasattr(risk_level, "value"):
        risk_level = risk_level.value

    scenario_context = {
        "failure_mode": failure_mode,
        "failure_mode_label": mode.get("label", failure_mode),
        "assume_no_spare": assume_no_spare,
        "defer_maintenance_days": defer_maintenance_days,
        "downtime_hours": downtime_hours,
        "affected_assets": affected_assets,
        "impact_summary": impact,
        "spare_status": spare_status,
    }

    # --- LangGraph orchestrator (scenario intent) ---
    query = (
        f"What happens if {code} ({equipment.name}) fails due to {mode.get('label', failure_mode)}? "
        f"Downtime {downtime_hours}h, {len(affected_assets)} downstream assets affected, "
        f"production loss {impact['total_production_loss_tons']} tons."
    )
    orch = await get_orchestrator().run(
        query=query,
        query_intent="scenario",
        page_context="Failure Scenario Simulator",
        equipment_context=equipment_context,
        sensor_reading=scenario_reading,
        spare_context=spares,
        scenario_context=scenario_context,
        operational_context={"failure_mode": failure_mode},
    )

    structured = orch.get("structured_output") or {}
    maintenance_plan = structured.get("maintenance_plan") or {}
    scenario_analysis = structured.get("scenario_analysis") or {}

    contingency = scenario_analysis.get("contingency_steps") or _build_contingency(
        code, failure_mode, affected_assets, downtime_hours, assume_no_spare
    )
    maintenance_recommendation = {
        "immediate_actions": maintenance_plan.get("immediate_actions", []),
        "short_term_actions": maintenance_plan.get("short_term_actions", []),
        "long_term_actions": maintenance_plan.get("long_term_actions", []),
        "monitoring_plan": maintenance_plan.get("monitoring_plan"),
        "ai_summary": orch.get("message", "")[:1200],
    }

    reasoning_panel = orch.get("reasoning_panel") or build_reasoning_panel(
        agent_thoughts=orch.get("agent_thoughts", []),
        agent_trace=orch.get("agent_trace", []),
        citations=orch.get("citations", []),
        query_intent="scenario",
        llm_provider=llm_service.last_provider,
        structured_output=structured,
    ).model_dump()

    result = {
        "equipment_id": equipment.id,
        "equipment_code": code,
        "equipment_name": equipment.name,
        "location": equipment.location,
        "scenario": failure_mode,
        "scenario_label": mode.get("label", failure_mode),
        "risk_level": risk_level,
        "baseline_rul_hours": round(baseline_rul, 1),
        "scenario_rul_hours": round(scenario_rul, 1),
        "failure_probability": round(failure_prob, 3),
        "anomaly_detected": anomaly.get("is_anomaly", False),
        "affected_assets": affected_assets,
        "affected_asset_codes": [a["equipment_code"] for a in affected_assets],
        "dependency_chain": _build_chain_view(code, affected_assets),
        "downtime_estimate_hours": impact["total_downtime_hours"],
        "source_downtime_hours": impact["source_downtime_hours"],
        "production_impact_tons": impact["total_production_loss_tons"],
        "source_production_loss_tons": impact["source_production_loss_tons"],
        "cascade_production_loss_tons": impact["cascade_production_loss_tons"],
        "cost_impact_inr": impact["total_cost_inr"],
        "direct_cost_inr": impact["direct_cost_inr"],
        "cascade_cost_inr": impact["cascade_cost_inr"],
        "spare_availability": {
            "status": spare_status,
            "assume_no_spare": assume_no_spare,
            "lead_time_days": lead_time,
            "parts": spares[:6],
            "low_stock_count": len(low_stock),
            "procurement_notes": risk.get("procurement_notes", []),
        },
        "contingency_plan": contingency,
        "maintenance_recommendation": maintenance_recommendation,
        "impact_summary": impact,
        "production_rate_tph": PRODUCTION_RATE_TPH.get(code, 0),
        "agent_trace": orch.get("agent_trace", []),
        "reasoning_panel": reasoning_panel,
        "llm_provider": llm_service.last_provider,
        "fleet_context": [{"code": a["code"], "name": a["name"]} for a in CANONICAL_FLEET],
    }

    run = FailureScenarioRun(
        equipment_id=equipment.id,
        user_id=user_id,
        failure_mode=failure_mode,
        assume_no_spare=assume_no_spare,
        defer_maintenance_days=defer_maintenance_days,
        result_json=result,
    )
    db.add(run)
    await db.flush()
    result["scenario_run_id"] = run.id
    return result


def _estimate_downtime(failure_mode: str, no_spare: bool, lead_time_days: int) -> float:
    base = {"bearing_failure": 12, "motor_overheat": 8, "pump_seizure": 16, "unplanned_shutdown": 24}.get(
        failure_mode, 12
    )
    spare_penalty = 48 if no_spare else max(0, (lead_time_days - 1) * 8)
    return float(base + spare_penalty)


def _build_contingency(
    code: str,
    failure_mode: str,
    affected: list[dict],
    downtime_hours: float,
    no_spare: bool,
) -> list[str]:
    steps = [
        f"T+0h — Declare {failure_mode.replace('_', ' ')} on {code}; isolate asset per SOP-MAINT-042",
        f"T+1h — Assess safe shutdown window; estimated repair {downtime_hours:.0f}h",
    ]
    if no_spare:
        steps.append("T+2h — Emergency procurement flagged; assume 48h+ lead time for critical spares")
    else:
        steps.append("T+2h — Verify spare parts kit staged at line-side store")
    if affected:
        downstream = ", ".join(a["equipment_code"] for a in affected[:4])
        steps.append(f"T+4h — Notify downstream production cells: {downstream}")
        steps.append("T+6h — Activate contingency rolling schedule; re-route hot metal if BF/RM impacted")
    steps.append("T+24h — Post-incident review with reliability engineering and update dependency register")
    return steps


def _build_chain_view(source: str, affected: list[dict]) -> list[dict]:
    chain = [{"equipment_code": source, "hop": 0, "role": "failed_asset", "severity": "critical"}]
    for a in affected:
        chain.append({
            "equipment_code": a["equipment_code"],
            "hop": a["hop"],
            "role": "downstream",
            "severity": a["severity"],
            "impact_score": a["impact_score"],
        })
    return chain
