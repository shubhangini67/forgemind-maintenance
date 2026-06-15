from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Alert, User
from app.schemas import (
    AlertResponse,
    ChatRequest,
    ChatResponse,
    ConversationDetail,
    ConversationSummary,
    DiagnosisRequest,
    DiagnosisResponse,
    FeedbackCreate,
    FeedbackStatsResponse,
)
from app.core.fleet import CANONICAL_CODES
from app.services.chat_service import (
    get_conversation_detail,
    list_user_conversations,
    process_chat,
    run_diagnosis,
)
from app.services.feedback_service import get_feedback_stats, save_feedback_event

from pydantic import BaseModel

from app.core.logbook_events import LogbookEventSource, LogbookEventType
from app.services.logbook_service import emit_logbook_event, sync_maintenance_schedule_logbook
from app.services.scenario_service import get_scenario_dependencies, simulate_failure
from app.services.decision_simulator_service import run_decision_simulation

router = APIRouter(tags=["wizard"])


class SimulateRequest(BaseModel):
    equipment_id: int
    failure_mode: str = "bearing_failure"
    defer_maintenance_days: int = 0
    assume_no_spare: bool = False


class DecisionSimulateRequest(BaseModel):
    equipment_id: int
    mode: str = "delay"  # delay | immediate_failure
    delay_hours: int = 72
    custom_delay_hours: int | None = None
    failure_mode: str = "bearing_failure"


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = await process_chat(db, current_user.id, request)
        return ChatResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"AI pipeline error: {exc}") from exc


@router.get("/chat/conversations", response_model=list[ConversationSummary])
async def chat_conversations(
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = await list_user_conversations(db, current_user.id, limit=limit)
    return [ConversationSummary(**r) for r in rows]


@router.get("/chat/conversations/{conversation_id}", response_model=ConversationDetail)
async def chat_conversation_detail(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        detail = await get_conversation_detail(db, current_user.id, conversation_id)
        return ConversationDetail(**detail)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/diagnose", response_model=DiagnosisResponse)
async def diagnose(
    request: DiagnosisRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        return await run_diagnosis(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/feedback")
async def feedback(
    body: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry = await save_feedback_event(db, current_user.id, body)
    return {"id": entry.id, "status": "saved", "fault_type": entry.fault_type}


@router.get("/feedback/stats", response_model=FeedbackStatsResponse)
async def feedback_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await get_feedback_stats(db)



@router.get("/simulate/dependencies")
async def simulate_dependencies(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await get_scenario_dependencies(db)


@router.post("/simulate")
async def simulate_scenario(
    body: SimulateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await simulate_failure(
            db,
            body.equipment_id,
            failure_mode=body.failure_mode,
            defer_maintenance_days=body.defer_maintenance_days,
            assume_no_spare=body.assume_no_spare,
            user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/simulate/decision")
async def simulate_decision(
    body: DecisionSimulateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await run_decision_simulation(
            db,
            body.equipment_id,
            mode=body.mode,
            delay_hours=body.delay_hours,
            custom_delay_hours=body.custom_delay_hours,
            failure_mode=body.failure_mode,
            user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/alerts", response_model=list[AlertResponse])
async def list_alerts(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    status: str | None = Query(None, description="open | resolved | all"),
    limit: int = Query(50, ge=1, le=200),
):
    q = select(Alert).order_by(desc(Alert.created_at))
    if status == "open":
        from app.models import AlertStatus
        q = q.where(Alert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]))
    elif status == "resolved":
        from app.models import AlertStatus
        q = q.where(Alert.status == AlertStatus.RESOLVED)
    result = await db.execute(q.limit(limit))
    return [AlertResponse.model_validate(a) for a in result.scalars().all()]


@router.get("/alerts/summary")
async def alerts_summary(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    from app.models import AlertLevel, AlertStatus

    open_count = await db.scalar(
        select(func.count()).select_from(Alert).where(Alert.status == AlertStatus.OPEN)
    ) or 0
    critical = await db.scalar(
        select(func.count()).select_from(Alert).where(
            Alert.status == AlertStatus.OPEN, Alert.level == AlertLevel.CRITICAL
        )
    ) or 0
    high = await db.scalar(
        select(func.count()).select_from(Alert).where(
            Alert.status == AlertStatus.OPEN, Alert.level == AlertLevel.HIGH
        )
    ) or 0
    warning = await db.scalar(
        select(func.count()).select_from(Alert).where(
            Alert.status == AlertStatus.OPEN, Alert.level == AlertLevel.WARNING
        )
    ) or 0
    return {"open": open_count, "critical": critical, "high": high, "warning": warning}


@router.get("/analytics/plant")
async def plant_analytics(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    from app.models import Equipment, Prediction, SensorData
    from app.services.business_impact_service import compute_plant_business_impact
    from app.services.equipment_service import resolve_equipment_health

    eq_result = await db.execute(
        select(Equipment).where(Equipment.equipment_code.in_(CANONICAL_CODES))
    )
    equipment = list(eq_result.scalars().all())
    rows = []
    for eq in equipment:
        sensor = (
            await db.execute(
                select(SensorData)
                .where(SensorData.equipment_id == eq.id)
                .order_by(desc(SensorData.timestamp))
                .limit(1)
            )
        ).scalar_one_or_none()
        health = await resolve_equipment_health(db, eq.id, sensor)
        pred = await db.scalar(
            select(Prediction.remaining_useful_life_hours)
            .where(Prediction.equipment_id == eq.id)
            .order_by(desc(Prediction.created_at))
            .limit(1)
        )
        s = sensor
        rows.append({
            "equipment_id": eq.id,
            "equipment_code": eq.equipment_code,
            "name": eq.name,
            "area": eq.location,
            "criticality": eq.criticality,
            "health_score": round(health, 1),
            "rul_hours": pred or 0,
            "temperature": s.temperature if s else None,
            "vibration": s.vibration if s else None,
        })
    rows.sort(key=lambda r: r["health_score"])
    avg_health = sum(r["health_score"] for r in rows) / max(len(rows), 1)

    business = await compute_plant_business_impact(db)
    fleet = business["fleet_summary"]

    return {
        "equipment": rows,
        "avg_health": round(avg_health, 1),
        "at_risk_count": len([r for r in rows if r["health_score"] < 55]),
        "roi": {
            "downtime_hours_prevented": round(fleet["total_avoided_loss_inr"] / 45000, 1),
            "estimated_savings_inr": fleet["total_estimated_savings_inr"],
            "maintenance_efficiency_gain_pct": round(min(35, (100 - avg_health) * 0.4), 1),
        },
        "business_impact": business,
    }


@router.get("/analytics/business-impact")
async def business_impact_analytics(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    from app.services.business_impact_service import compute_plant_business_impact

    return await compute_plant_business_impact(db)


@router.get("/analytics/executive-summary")
async def executive_summary(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    from app.services.business_impact_service import build_executive_summary_narrative, compute_plant_business_impact

    data = await compute_plant_business_impact(db)
    return {
        "summary": data["fleet_summary"],
        "critical_assets": data["critical_assets"],
        "narrative": build_executive_summary_narrative(data),
        "methodology": data["methodology"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


class ReminderCreate(BaseModel):
    equipment_id: int
    title: str
    reminder_at: str
    notes: str = ""


@router.get("/scheduler/reminders")
async def list_reminders(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    from app.models import Equipment, LogbookEntry

    result = await db.execute(
        select(LogbookEntry)
        .where(LogbookEntry.entry_type == "reminder")
        .order_by(desc(LogbookEntry.created_at))
        .limit(50)
    )
    eq_result = await db.execute(select(Equipment).where(Equipment.equipment_code.in_(CANONICAL_CODES)))
    eq_map = {e.id: e.equipment_code for e in eq_result.scalars().all()}
    return [
        {
            "id": e.id,
            "equipment_id": e.equipment_id,
            "equipment_code": eq_map.get(e.equipment_id),
            "title": e.title,
            "notes": e.description,
            "reminder_at": (e.metadata_json or {}).get("reminder_at"),
            "observed_by": e.observed_by,
            "created_at": e.created_at,
        }
        for e in result.scalars().all()
    ]


@router.post("/scheduler/reminders")
async def create_reminder(
    body: ReminderCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entry = await emit_logbook_event(
        db,
        event=LogbookEventType.MAINTENANCE_SCHEDULED,
        equipment_id=body.equipment_id,
        title=body.title[:255],
        description=body.notes[:2000] if body.notes else f"Reminder scheduled for {body.reminder_at}",
        observed_by=user.full_name or "Engineer",
        source=LogbookEventSource.SCHEDULER,
        entry_type="reminder",
        metadata={"reminder_at": body.reminder_at, "manual": True},
    )
    return {"id": entry.id if entry else None, "status": "created"}


@router.get("/scheduler/plan")
async def maintenance_schedule(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    from datetime import datetime, timedelta, timezone
    from app.models import Equipment, SparePart
    from app.services.equipment_service import resolve_equipment_health
    from app.services.live_stream import peek_reading
    from app.services.ml.predictive_engine import pm_engine, risk_engine
    from app.services.procurement_risk import spare_procurement_profile

    eq_result = await db.execute(
        select(Equipment)
        .where(Equipment.equipment_code.in_(CANONICAL_CODES))
        .order_by(Equipment.id)
    )
    equipment = list(eq_result.scalars().all())
    tasks = []
    base = datetime.now(timezone.utc)
    for i, eq in enumerate(equipment):
        health = await resolve_equipment_health(db, eq.id)
        meta = eq.metadata_json or {}
        spare_rows = await db.execute(select(SparePart).where(SparePart.equipment_type == eq.equipment_type))
        spares = [
            {
                "part_number": s.part_number,
                "name": s.name,
                "quantity_available": s.quantity_available,
                "reorder_level": s.reorder_level,
                "lead_time_days": s.lead_time_days,
            }
            for s in spare_rows.scalars().all()
        ]
        profile = spare_procurement_profile(spares)
        live = peek_reading(eq.id)
        live_pred = pm_engine.predict_rul({
            "temperature": live["temperature"],
            "vibration": live["vibration"],
            "pressure": live["pressure"],
            "motor_current": live["motor_current"],
            "health_indicator": live["health_indicator"],
        })
        rul_hours = live_pred.get("remaining_useful_life_hours") or live.get("rul_hours")
        risk = risk_engine.compute(
            criticality=eq.criticality,
            failure_probability=float(live_pred.get("failure_probability") or 0.5),
            downtime_cost=float(meta.get("downtime_cost", 50000)),
            spare_availability=profile["spare_stock"],
            lead_time_days=profile["lead_time_days"],
            rul_hours=float(rul_hours) if rul_hours is not None else None,
            reorder_level=profile["reorder_level"],
        )
        risk_level = risk["risk_level"]
        rl = risk_level.value if hasattr(risk_level, "value") else str(risk_level)
        urgency = "critical" if rl == "critical" or risk["procurement_risk"] == "critical" else "high" if rl == "high" or risk["procurement_risk"] == "high" else "planned"
        start = base + timedelta(days=i, hours=health % 8)
        duration_h = 4 if urgency == "critical" else 8 if urgency == "high" else 16
        task_label = "Emergency" if urgency == "critical" else "Preventive"
        if risk["escalated"]:
            task_label = "Procurement-critical"
        tasks.append({
            "id": eq.id,
            "equipment_code": eq.equipment_code,
            "name": eq.name,
            "task": f"{task_label} inspection — {eq.name}",
            "urgency": urgency,
            "start": start.isoformat(),
            "end": (start + timedelta(hours=duration_h)).isoformat(),
            "duration_hours": duration_h,
            "spares_available": profile["spare_stock"],
            "lead_time_days": profile["lead_time_days"],
            "procurement_risk": risk["procurement_risk"],
            "business_impact_inr": risk["business_impact_inr"],
            "rul_days": risk["rul_days"],
            "risk_escalated": risk["escalated"],
            "escalation_reason": risk["escalation_reason"],
            "critical_spare_part": profile["critical_part_number"],
            "health_score": health,
        })
    tasks.sort(key=lambda t: ({"critical": 0, "high": 1, "planned": 2}[t["urgency"]], t["health_score"]))
    logged = await sync_maintenance_schedule_logbook(db, tasks)
    return {"tasks": tasks, "horizon_days": 7, "logbook_entries_created": logged}
