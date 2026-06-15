from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, AlertStatus, Report, SparePart
from app.schemas import ReportRequest
from app.services.agents.orchestrator import get_orchestrator
from app.services.equipment_service import get_dashboard_summary, get_equipment, get_latest_predictions, get_plant_priority
from app.services.live_stream import get_next_reading
from app.services.llm_service import llm_service
from app.core.logbook_events import LogbookEventSource, LogbookEventType
from app.services.logbook_service import emit_logbook_event
from app.services.operational_context import load_operational_context
from app.services.rag.knowledge_engine import get_rag_engine


async def _list_spares(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(SparePart).order_by(SparePart.quantity_available))
    return [
        {
            "part_number": s.part_number,
            "name": s.name,
            "quantity_available": s.quantity_available,
            "reorder_level": s.reorder_level,
        }
        for s in result.scalars().all()
    ]


async def _open_alerts(db: AsyncSession, equipment_id: int | None = None) -> list[dict]:
    q = select(Alert).where(Alert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED])).order_by(desc(Alert.created_at)).limit(10)
    if equipment_id:
        q = q.where(Alert.equipment_id == equipment_id)
    result = await db.execute(q)
    return [
        {"id": a.id, "equipment_id": a.equipment_id, "level": a.level.value, "title": a.title, "message": a.message[:200]}
        for a in result.scalars().all()
    ]


async def generate_report(db: AsyncSession, request: ReportRequest) -> Report:
    now = datetime.now(timezone.utc).isoformat()
    report_type = request.report_type or "maintenance"
    equipment = await get_equipment(db, request.equipment_id) if request.equipment_id else None
    operational = await load_operational_context(db, request.equipment_id) if request.equipment_id else {}
    open_alerts = await _open_alerts(db, request.equipment_id)
    spares = await _list_spares(db)
    rag = get_rag_engine()

    content: dict = {
        "report_meta": {
            "report_type": report_type,
            "generated_at": now,
            "generated_by": "LangGraph Report Agent + XGBoost + RAG",
        },
    }

    orch_output: dict = {}
    agent_trace: list[str] = []
    citations: list[dict] = []

    if equipment and report_type in ("maintenance", "abnormal", "diagnosis"):
        sensor = get_next_reading(equipment.id)
        eq_ctx = {
            "id": equipment.id,
            "equipment_code": equipment.equipment_code,
            "name": equipment.name,
            "equipment_type": equipment.equipment_type,
            "criticality": equipment.criticality,
            "location": equipment.location,
            "downtime_cost": (equipment.metadata_json or {}).get("downtime_cost", 50000),
        }
        query = {
            "maintenance": f"Generate maintenance report for {equipment.equipment_code} including RUL, root cause, and actions",
            "abnormal": f"Generate abnormal alert report for {equipment.equipment_code} — open alerts and anomalies",
            "diagnosis": f"Full diagnostic report for {equipment.equipment_code}",
        }.get(report_type, f"Report for {equipment.equipment_code}")

        if report_type == "abnormal" and not open_alerts:
            rag_results = rag.hybrid_search(f"failure abnormal {equipment.equipment_type}", limit=3, equipment_type=equipment.equipment_type)
        else:
            rag_results = rag.hybrid_search(query, limit=5, equipment_type=equipment.equipment_type)

        try:
            orch = await get_orchestrator().run(
                query=query,
                equipment_context=eq_ctx,
                sensor_reading=sensor,
                spare_context=spares,
                operational_context=operational,
            )
            orch_output = orch.get("structured_output") or {}
            agent_trace = orch.get("agent_trace") or []
            citations = orch.get("citations") or []
            if not citations and rag_results:
                citations = [
                    {"source": r["source"], "document_type": r["document_type"], "excerpt": r["excerpt"][:300], "score": r["score"]}
                    for r in rag_results[:5]
                ]
        except Exception as exc:
            orch_output = {"error": str(exc)[:200]}

        prediction = orch_output.get("prediction") or {}
        if not prediction:
            pred_row = await get_latest_predictions(db, equipment.id)
            if pred_row:
                prediction = {
                    "failure_probability": pred_row.failure_probability,
                    "rul_hours": pred_row.remaining_useful_life_hours,
                    "risk_level": pred_row.risk_level.value if hasattr(pred_row.risk_level, "value") else str(pred_row.risk_level),
                }

        diagnosis = orch_output.get("diagnosis") or {}
        plan = orch_output.get("maintenance_plan") or {}
        risk_assess = orch_output.get("risk_assessment") or {}
        downtime_cost = eq_ctx.get("downtime_cost", 50000)
        rul_h = prediction.get("remaining_useful_life_hours") or prediction.get("rul_hours") or 0
        delay_h = operational.get("total_recent_delay_hours") or 0

        content.update({
            "asset": {
                "code": equipment.equipment_code,
                "name": equipment.name,
                "location": equipment.location,
                "criticality": equipment.criticality,
                "cmapss_unit": (equipment.metadata_json or {}).get("cmapss_unit"),
            },
            "risk": {
                "risk_level": prediction.get("risk_level") or risk_assess.get("risk_level"),
                "failure_probability": prediction.get("failure_probability"),
                "open_alerts": open_alerts,
            },
            "rul": {
                "rul_hours": rul_h,
                "degradation_score": prediction.get("degradation_score"),
                "sensor_snapshot": sensor,
            },
            "root_cause": {
                "probable_causes": diagnosis.get("probable_causes", []),
                "root_cause_analysis": diagnosis.get("root_cause_analysis", ""),
                "operational_incidents": operational.get("failure_incidents", [])[:3],
                "delay_logs": operational.get("delay_logs", [])[:3],
            },
            "retrieved_documents": citations,
            "spares": {
                "available": [s for s in spares if s["quantity_available"] > 0][:8],
                "procurement_notes": risk_assess.get("procurement_notes", []),
                "risk_factors": risk_assess.get("risk_factors", []),
            },
            "recommended_actions": {
                "immediate": plan.get("immediate_actions", []),
                "short_term": plan.get("short_term_actions", []),
                "long_term": plan.get("long_term_actions", []),
            },
            "cost_impact": {
                "estimated_downtime_hours": min(float(rul_h or 24), 72),
                "estimated_cost_inr": int(downtime_cost * min(float(rul_h or 24), 72) / 24),
                "recent_delay_hours": delay_h,
            },
            "business_impact": {
                "estimated_impact_inr": risk_assess.get("business_impact_inr"),
                "procurement_risk": risk_assess.get("procurement_risk"),
            },
            "agent_trace": agent_trace,
        })

    elif report_type == "executive" or not request.equipment_id:
        from app.services.business_impact_service import build_executive_summary_narrative, compute_plant_business_impact

        summary = await get_dashboard_summary(db)
        priority = await get_plant_priority(db)
        business = await compute_plant_business_impact(db)
        content["plant_summary"] = summary.model_dump(mode="json")
        content["priority_queue"] = priority[:5]
        content["open_alerts"] = open_alerts
        content["business_impact"] = business
        content["executive_summary"] = {
            "fleet": business["fleet_summary"],
            "critical_assets": business["critical_assets"],
            "narrative": build_executive_summary_narrative(business),
            "methodology": business["methodology"],
        }
        content["asset"] = {"code": "PLANT", "name": "Full Plant Overview"}

    prompt = f"""Write a concise executive maintenance report narrative (max 400 words) for Tata Steel.
Report type: {report_type}
Structured data: {str(content)[:6000]}
Include: asset status, RUL if present, top risks, recommended actions, cost impact."""
    try:
        narrative = await llm_service.generate(prompt)
    except Exception:
        narrative = _fallback_narrative(content, report_type)
    content["narrative"] = narrative

    title = request.title or {
        "maintenance": f"Maintenance Report — {equipment.equipment_code if equipment else 'Plant'}",
        "abnormal": f"Abnormal Alert Report — {equipment.equipment_code if equipment else 'Plant'}",
        "executive": "Executive Plant Overview",
        "diagnosis": f"AI Diagnosis Report — {equipment.equipment_code if equipment else 'Asset'}",
    }.get(report_type, f"{report_type.title()} Report")

    report = Report(
        report_type=report_type,
        title=title,
        equipment_id=request.equipment_id,
        content=content,
        generated_by="report_agent",
    )
    db.add(report)
    await db.flush()

    if request.equipment_id:
        await emit_logbook_event(
            db,
            event=LogbookEventType.REPORT_GENERATED,
            equipment_id=request.equipment_id,
            title=f"Report generated: {title[:120]}",
            description=narrative[:1500],
            observed_by="Report Agent",
            source=LogbookEventSource.REPORT,
            source_id=report.id,
            metadata={"report_type": report_type},
        )

    return report


def _fallback_narrative(content: dict, report_type: str) -> str:
    asset = content.get("asset") or {}
    rul = content.get("rul") or {}
    risk = content.get("risk") or {}
    actions = content.get("recommended_actions") or {}
    immediate = actions.get("immediate") or []
    return (
        f"## {report_type.title()} Report\n\n"
        f"Asset: {asset.get('code', 'N/A')} — {asset.get('name', '')}\n"
        f"RUL: {rul.get('rul_hours', 'N/A')} hours | Risk: {risk.get('risk_level', 'N/A')}\n\n"
        f"Immediate actions:\n" + "\n".join(f"- {a}" for a in immediate[:4])
    )
