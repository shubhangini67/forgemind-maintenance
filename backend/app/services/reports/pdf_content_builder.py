"""Build normalized PDF content payloads for all report types."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, Equipment
from app.services.business_impact_service import build_executive_summary_narrative, compute_plant_business_impact
from app.services.equipment_service import get_equipment, get_plant_priority


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _base_meta(report_type: str, title: str) -> dict:
    return {
        "report_type": report_type,
        "generated_at": _now(),
        "title": title,
        "generated_by": "Tata Steel Maintenance Wizard",
    }


def normalize_pdf_content(raw: dict, *, report_type: str, title: str) -> dict:
    """Ensure all required PDF sections exist."""
    content = dict(raw)
    content.setdefault("report_meta", _base_meta(report_type, title))
    content["report_meta"]["report_type"] = report_type
    content["report_meta"]["title"] = title
    for key in (
        "asset",
        "diagnosis",
        "rul",
        "risk",
        "root_cause",
        "citations",
        "maintenance_recommendation",
        "spare_status",
        "business_impact",
    ):
        content.setdefault(key, {} if key != "citations" else [])
    if isinstance(content.get("diagnosis"), dict):
        content["diagnosis"] = content["diagnosis"].get("summary") or str(content["diagnosis"])
    if content.get("retrieved_documents") and not content.get("citations"):
        content["citations"] = content["retrieved_documents"]
    if content.get("recommended_actions") and not content.get("maintenance_recommendation"):
        ra = content["recommended_actions"]
        content["maintenance_recommendation"] = {
            "immediate_actions": ra.get("immediate", []),
            "short_term_actions": ra.get("short_term", []),
            "long_term_actions": ra.get("long_term", []),
        }
    if content.get("spares") and not content.get("spare_status"):
        content["spare_status"] = content["spares"]
    if content.get("cost_impact") and not content.get("business_impact"):
        content["business_impact"] = content["cost_impact"]
    return content


def from_diagnosis_payload(payload: dict, equipment: Equipment | None = None) -> dict:
    title = f"Diagnosis Report — {payload.get('equipment_code') or equipment.equipment_code if equipment else 'Asset'}"
    causes = payload.get("probable_causes") or []
    return normalize_pdf_content(
        {
            "asset": {
                "code": payload.get("equipment_code") or (equipment.equipment_code if equipment else "—"),
                "name": payload.get("equipment_name") or (equipment.name if equipment else ""),
                "location": equipment.location if equipment else "",
                "criticality": equipment.criticality if equipment else payload.get("criticality"),
            },
            "diagnosis": payload.get("ai_summary") or payload.get("root_cause_analysis") or "",
            "rul": {
                "rul_hours": payload.get("remaining_useful_life_hours"),
                "failure_probability": payload.get("failure_probability"),
            },
            "risk": {
                "risk_level": payload.get("risk_level"),
                "failure_probability": payload.get("failure_probability"),
                "escalated": payload.get("risk_escalated"),
                "escalation_reason": payload.get("escalation_reason"),
            },
            "root_cause": {
                "probable_causes": causes,
                "root_cause_analysis": payload.get("root_cause_analysis", ""),
            },
            "citations": payload.get("citations") or [],
            "maintenance_recommendation": {
                "immediate_actions": payload.get("immediate_actions") or [],
                "short_term_actions": payload.get("short_term_actions") or [],
                "long_term_actions": payload.get("long_term_actions") or [],
                "monitoring_plan": payload.get("monitoring_plan"),
            },
            "spare_status": {
                "spare_stock": payload.get("spare_stock"),
                "lead_time_days": payload.get("lead_time_days"),
                "procurement_risk": payload.get("procurement_risk"),
                "critical_spare_part": payload.get("critical_spare_part"),
            },
            "business_impact": {
                "estimated_impact_inr": payload.get("business_impact_inr"),
            },
        },
        report_type="diagnosis",
        title=title,
    )


def from_scenario_payload(payload: dict) -> dict:
    title = f"Failure Scenario — {payload.get('equipment_code', 'Asset')}"
    maint = payload.get("maintenance_recommendation") or {}
    spares = payload.get("spare_availability") or {}
    return normalize_pdf_content(
        {
            "asset": {
                "code": payload.get("equipment_code"),
                "name": payload.get("equipment_name"),
                "location": payload.get("location"),
            },
            "diagnosis": maint.get("ai_summary") or payload.get("scenario_label") or "",
            "rul": {
                "baseline_rul_hours": payload.get("baseline_rul_hours"),
                "scenario_rul_hours": payload.get("scenario_rul_hours"),
                "failure_probability": payload.get("failure_probability"),
            },
            "risk": {"risk_level": payload.get("risk_level"), "failure_probability": payload.get("failure_probability")},
            "root_cause": {
                "probable_causes": [{"cause": f"Simulated {payload.get('scenario_label', 'failure')}", "confidence": 0.9}],
                "root_cause_analysis": f"Affected assets: {', '.join(payload.get('affected_asset_codes') or [])}",
            },
            "citations": payload.get("citations") or [],
            "maintenance_recommendation": maint,
            "spare_status": spares,
            "business_impact": {
                "downtime_hours": payload.get("downtime_estimate_hours"),
                "production_loss_tons": payload.get("production_impact_tons"),
                "cost_impact_inr": payload.get("cost_impact_inr"),
                "direct_cost_inr": payload.get("direct_cost_inr"),
                "cascade_cost_inr": payload.get("cascade_cost_inr"),
            },
            "scenario": {
                "failure_mode": payload.get("scenario_label"),
                "affected_assets": payload.get("affected_assets"),
                "contingency": payload.get("contingency_plan") or payload.get("contingency_steps"),
            },
        },
        report_type="scenario",
        title=title,
    )


def from_decision_payload(payload: dict) -> dict:
    title = f"Decision Simulator — {payload.get('equipment_code', 'Asset')}"
    selected = payload.get("selected_scenario") or {}
    rec = payload.get("recommendation") or {}
    fin = payload.get("financial_impact") or {}
    spares = payload.get("spare_availability") or {}
    maint = payload.get("maintenance_recommendation") or {}
    comparison = payload.get("comparison") or []
    delay_label = payload.get("selected_delay_label") or selected.get("label") or "—"
    delay_hours = payload.get("selected_delay_hours")
    comp_lines = [
        f"{c.get('label')}: risk {c.get('risk_level')}, "
        f"downtime {c.get('downtime_hours')}h, "
        f"cost ₹{c.get('net_exposure_inr', 0):,}"
        + (" ★ BEST" if c.get("is_best") else "")
        + (" ◆ SELECTED" if c.get("id") == payload.get("selected_scenario_id") else "")
        for c in comparison
    ]
    reasoning = payload.get("reasoning_chain") or []
    reasoning_text = "\n".join(f"{r.get('step')}: {r.get('detail')}" for r in reasoning)
    return normalize_pdf_content(
        {
            "asset": {
                "code": payload.get("equipment_code"),
                "name": payload.get("equipment_name"),
                "location": payload.get("location"),
                "criticality": payload.get("criticality"),
            },
            "diagnosis": (
                f"Simulated scenario: {delay_label}\n\n"
                f"{rec.get('reason') or maint.get('ai_summary') or ''}"
            ),
            "rul": {
                "baseline_rul_hours": selected.get("baseline_rul_hours"),
                "baseline_rul_days": selected.get("baseline_rul_days"),
                "rul_hours": selected.get("rul_hours"),
                "rul_days": selected.get("rul_days"),
                "failure_probability": (selected.get("failure_probability_pct") or 0) / 100,
            },
            "risk": {
                "risk_level": selected.get("risk_level"),
                "risk_escalation": selected.get("risk_escalation"),
                "failure_probability": (selected.get("failure_probability_pct") or 0) / 100,
                "escalation_reason": selected.get("escalation_reason"),
            },
            "root_cause": {
                "probable_causes": [{"cause": rec.get("action", "Maintenance decision"), "confidence": (rec.get("confidence_pct") or 85) / 100}],
                "root_cause_analysis": reasoning_text,
            },
            "maintenance_recommendation": {
                **maint,
                "immediate_actions": maint.get("immediate_actions") or [rec.get("action", "")],
            },
            "spare_status": spares,
            "business_impact": {
                "downtime_hours": selected.get("downtime_hours"),
                "production_loss_tons": selected.get("production_loss_tons"),
                "downtime_cost_inr": fin.get("downtime_cost_inr"),
                "maintenance_cost_inr": fin.get("maintenance_cost_inr"),
                "avoided_loss_inr": fin.get("avoided_loss_inr"),
                "net_exposure_inr": fin.get("net_exposure_inr"),
            },
            "scenario": {
                "failure_mode": payload.get("mode"),
                "delay_hours": delay_hours,
                "delay_label": delay_label,
                "scenario_label": selected.get("label"),
                "selected_scenario_id": payload.get("selected_scenario_id"),
                "affected_assets": payload.get("downstream_impact", {}).get("affected_details"),
                "contingency": payload.get("contingency_plan"),
                "comparison": comp_lines,
            },
            "narrative": (
                f"Simulated scenario: {delay_label}"
                + (f" ({delay_hours} hours)" if delay_hours is not None else "")
                + f"\n\nAI Recommendation: {rec.get('action')}\n\n{rec.get('reason')}"
            ),
        },
        report_type="decision",
        title=title,
    )


def from_priority_item(item: dict) -> dict:
    title = f"Priority Report — {item.get('equipment_code', 'Asset')}"
    return normalize_pdf_content(
        {
            "asset": {
                "code": item.get("equipment_code"),
                "name": item.get("equipment_name") or item.get("name"),
                "location": item.get("location") or item.get("plant_area"),
                "criticality": item.get("criticality"),
            },
            "diagnosis": f"Priority score {item.get('priority_score')} — recommended: {item.get('recommended_action')}",
            "rul": {"rul_hours": item.get("rul_hours"), "rul_days": item.get("rul_days")},
            "risk": {
                "risk_level": item.get("risk_level"),
                "active_alerts": item.get("active_alerts"),
                "critical_alerts": item.get("critical_alerts"),
                "escalated": item.get("risk_escalated"),
                "escalation_reason": item.get("escalation_reason"),
            },
            "root_cause": {
                "probable_causes": [
                    {"cause": f"Health {item.get('health_score')}% with {item.get('active_alerts', 0)} active alerts", "confidence": 0.85}
                ],
            },
            "maintenance_recommendation": {
                "immediate_actions": [item.get("recommended_action", "Review priority queue")],
            },
            "spare_status": {
                "spare_stock": item.get("spare_stock"),
                "lead_time_days": item.get("lead_time_days"),
                "procurement_risk": item.get("procurement_risk"),
                "critical_spare_part": item.get("critical_spare_part"),
                "critical_spares_available": item.get("critical_spares_available"),
            },
            "business_impact": {"estimated_impact_inr": item.get("business_impact_inr")},
        },
        report_type="priority",
        title=title,
    )


def from_alert(alert: Alert, equipment: Equipment) -> dict:
    title = f"Alert Report — {equipment.equipment_code}"
    return normalize_pdf_content(
        {
            "asset": {
                "code": equipment.equipment_code,
                "name": equipment.name,
                "location": equipment.location,
                "criticality": equipment.criticality,
            },
            "diagnosis": alert.message,
            "risk": {
                "alert_level": alert.level.value if hasattr(alert.level, "value") else str(alert.level),
                "status": alert.status.value if hasattr(alert.status, "value") else str(alert.status),
                "risk_level": alert.risk_level.value if alert.risk_level and hasattr(alert.risk_level, "value") else None,
            },
            "root_cause": {"probable_causes": [{"cause": alert.title, "confidence": 0.8}]},
            "maintenance_recommendation": {
                "immediate_actions": [
                    "Acknowledge alert and assign maintenance engineer",
                    "Inspect asset per alert message",
                    "Verify spare availability before intervention",
                ],
            },
            "business_impact": {
                "downtime_cost_per_day_inr": (equipment.metadata_json or {}).get("downtime_cost"),
            },
        },
        report_type="alert",
        title=title,
    )


def from_maintenance_plan(tasks: list[dict], equipment_id: int | None = None) -> dict:
    if equipment_id:
        tasks = [t for t in tasks if t.get("id") == equipment_id or t.get("equipment_id") == equipment_id]
    top = tasks[0] if tasks else {}
    title = f"Maintenance Plan — {top.get('equipment_code', 'Plant')}" if equipment_id else "Maintenance Plan — 7-Day Schedule"
    immediate = [f"{t.get('equipment_code')}: {t.get('task')} ({t.get('urgency')})" for t in tasks[:8]]
    return normalize_pdf_content(
        {
            "asset": {
                "code": top.get("equipment_code", "PLANT"),
                "name": top.get("name", "Scheduled maintenance"),
            },
            "diagnosis": f"{len(tasks)} tasks in 7-day horizon",
            "rul": {"rul_days": top.get("rul_days")},
            "risk": {"urgency": top.get("urgency"), "health_score": top.get("health_score")},
            "maintenance_recommendation": {
                "immediate_actions": immediate,
                "short_term_actions": [f"Window: {t.get('start', '')[:10]} — {t.get('end', '')[:10]}" for t in tasks[:5]],
            },
            "spare_status": {
                "spares_available": top.get("spares_available"),
                "lead_time_days": top.get("lead_time_days"),
                "procurement_risk": top.get("procurement_risk"),
            },
            "business_impact": {"estimated_impact_inr": top.get("business_impact_inr")},
            "schedule_tasks": tasks,
        },
        report_type="maintenance_plan",
        title=title,
    )


async def build_executive_pdf_content(db: AsyncSession) -> dict:
    business = await compute_plant_business_impact(db)
    narrative = build_executive_summary_narrative(business)
    priority = await get_plant_priority(db)
    title = "Executive Summary — Business Impact"
    return normalize_pdf_content(
        {
            "asset": {"code": "PLANT", "name": "Tata Steel Jamshedpur — Critical Fleet"},
            "diagnosis": narrative,
            "narrative": narrative,
            "executive_summary": business,
            "business_impact": business.get("fleet_summary", {}),
            "maintenance_recommendation": {
                "immediate_actions": [
                    f"{a['equipment_code']}: ROI {a['roi_pct']}% — savings ₹{a['estimated_savings_inr']:,}"
                    for a in business.get("critical_assets", [])[:5]
                ],
            },
            "priority_queue": priority[:5],
            "risk": {"critical_asset_count": business["fleet_summary"].get("critical_asset_count")},
        },
        report_type="executive",
        title=title,
    )


async def build_pdf_content(
    db: AsyncSession,
    *,
    report_type: str,
    equipment_id: int | None = None,
    alert_id: int | None = None,
    payload: dict | None = None,
    title: str | None = None,
) -> dict:
    """Resolve PDF content from payload or database."""
    if payload:
        builders = {
            "diagnosis": lambda: from_diagnosis_payload(payload),
            "scenario": lambda: from_scenario_payload(payload),
            "decision": lambda: from_decision_payload(payload),
            "priority": lambda: from_priority_item(payload),
            "maintenance_plan": lambda: from_maintenance_plan(payload.get("tasks") or [payload], equipment_id),
            "alert": lambda: from_alert_payload(payload),
        }
        if report_type in builders:
            content = builders[report_type]()
            if title:
                content["report_meta"]["title"] = title
            return content

    if report_type == "executive":
        content = await build_executive_pdf_content(db)
        if title:
            content["report_meta"]["title"] = title
        return content

    if report_type == "alert" and alert_id:
        alert = await db.get(Alert, alert_id)
        if not alert:
            raise ValueError("Alert not found")
        equipment = await get_equipment(db, alert.equipment_id)
        content = from_alert(alert, equipment)
        if title:
            content["report_meta"]["title"] = title
        return content

    if report_type == "priority" and equipment_id:
        priority = await get_plant_priority(db)
        item = next((p for p in priority if p["equipment_id"] == equipment_id), None)
        if not item:
            raise ValueError("Equipment not in priority queue")
        content = from_priority_item(item)
        if title:
            content["report_meta"]["title"] = title
        return content

    if report_type == "maintenance_plan":
        if not payload or not payload.get("tasks"):
            raise ValueError("maintenance_plan PDF requires payload.tasks from scheduler")
        content = from_maintenance_plan(payload["tasks"], equipment_id)
        if title:
            content["report_meta"]["title"] = title
        return content

    raise ValueError(f"Cannot build PDF for report_type={report_type}")


def from_alert_payload(payload: dict) -> dict:
    title = f"Alert Report — {payload.get('equipment_code', 'Asset')}"
    return normalize_pdf_content(
        {
            "asset": {
                "code": payload.get("equipment_code"),
                "name": payload.get("equipment_name"),
                "location": payload.get("location"),
            },
            "diagnosis": payload.get("message") or payload.get("title"),
            "risk": {
                "alert_level": payload.get("level"),
                "status": payload.get("status"),
            },
            "root_cause": {"probable_causes": [{"cause": payload.get("title", "Alert"), "confidence": 0.8}]},
            "maintenance_recommendation": {
                "immediate_actions": payload.get("recommended_actions") or [
                    "Acknowledge and inspect asset",
                    "Review sensor readings on Live Monitor",
                ],
            },
        },
        report_type="alert",
        title=title,
    )
