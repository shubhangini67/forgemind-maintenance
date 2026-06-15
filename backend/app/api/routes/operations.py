"""Logbook, procurement, alerts, live monitoring routes."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.api.deps import get_current_user, require_roles
from app.db.session import AsyncSessionLocal, get_db
from app.models import Alert, AlertStatus, DelayLog, Equipment, FailureHistory, LogbookEntry, MaintenanceRecord, ProcurementRequest, SparePart, User
from app.services.alerts.alert_engine import process_sensor_and_alert
from app.core.logbook_events import LogbookEventSource, LogbookEventType
from app.services.logbook_service import (
    emit_logbook_event,
    get_equipment_timeline,
    get_logbook_summary,
    serialize_logbook_entry,
)
from app.services.equipment_service import ingest_sensor_reading
from app.services.live_stream import get_next_reading, stream_readings

router = APIRouter(tags=["operations"])


# --- Live monitoring ---

@router.get("/monitor/live/{equipment_id}")
async def live_snapshot(
    equipment_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    reading = get_next_reading(equipment_id)
    if not reading:
        raise HTTPException(404, "No stream data")
    result = await process_sensor_and_alert(
        db,
        equipment_id,
        {
            "temperature": reading["temperature"],
            "vibration": reading["vibration"],
            "pressure": reading["pressure"],
            "motor_current": reading["motor_current"],
            "health_indicator": reading["health_indicator"],
        },
    )
    await ingest_sensor_reading(db, equipment_id, reading)
    pred = result.get("prediction") or {}
    return {
        **reading,
        "ml": {
            "risk_level": str(pred.get("risk_level", "")).replace("RiskLevel.", "").lower(),
            "failure_probability": pred.get("failure_probability"),
            "remaining_useful_life_hours": pred.get("remaining_useful_life_hours"),
            "alert_id": result.get("alert_id"),
        },
    }


@router.websocket("/ws/monitor/{equipment_id}")
async def ws_monitor(websocket: WebSocket, equipment_id: int, token: str = Query(...)):
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    try:
        async for reading in stream_readings(equipment_id, interval=2.0):
            async with AsyncSessionLocal() as db:
                ml = await process_sensor_and_alert(
                    db,
                    equipment_id,
                    {
                        "temperature": reading["temperature"],
                        "vibration": reading["vibration"],
                        "pressure": reading["pressure"],
                        "motor_current": reading["motor_current"],
                        "health_indicator": reading["health_indicator"],
                    },
                )
                await ingest_sensor_reading(db, equipment_id, reading)
                await db.commit()
            pred = ml.get("prediction") or {}
            await websocket.send_json({
                **reading,
                "ml": {
                    "risk_level": str(pred.get("risk_level", "")).replace("RiskLevel.", "").lower(),
                    "failure_probability": pred.get("failure_probability"),
                    "remaining_useful_life_hours": pred.get("remaining_useful_life_hours"),
                    "alert_id": ml.get("alert_id"),
                },
            })
    except WebSocketDisconnect:
        pass


# --- Logbook ---

@router.get("/logbook")
async def list_logbook(
    equipment_id: int | None = None,
    entry_type: str | None = None,
    auto_only: bool | None = None,
    source_event: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(LogbookEntry).order_by(desc(LogbookEntry.created_at)).limit(limit)
    if equipment_id:
        q = q.where(LogbookEntry.equipment_id == equipment_id)
    if entry_type:
        q = q.where(LogbookEntry.entry_type == entry_type)
    if auto_only is True:
        q = q.where(LogbookEntry.auto_generated.is_(True))
    elif auto_only is False:
        q = q.where(LogbookEntry.auto_generated.is_(False))
    if source_event:
        q = q.where(LogbookEntry.source_event == source_event)
    result = await db.execute(q)
    entries = list(result.scalars().all())
    # Legacy rows may only have auto_generated in metadata_json
    if auto_only is True:
        entries = [e for e in entries if e.auto_generated or (e.metadata_json or {}).get("auto_generated")]
    elif auto_only is False:
        entries = [e for e in entries if not e.auto_generated and not (e.metadata_json or {}).get("auto_generated")]
    eq_result = await db.execute(select(Equipment))
    eq_map = {e.id: e.equipment_code for e in eq_result.scalars().all()}
    return [serialize_logbook_entry(e, eq_map.get(e.equipment_id)) for e in entries]


@router.get("/logbook/summary")
async def logbook_summary(
    equipment_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await get_logbook_summary(db, equipment_id)


@router.get("/logbook/timeline/{equipment_id}")
async def logbook_timeline(
    equipment_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    timeline = await get_equipment_timeline(db, equipment_id, limit=limit)
    if not timeline:
        eq = await db.get(Equipment, equipment_id)
        if not eq:
            raise HTTPException(404, "Equipment not found")
    return {"equipment_id": equipment_id, "entries": timeline}


@router.post("/logbook")
async def create_logbook_entry(
    body: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entry = await emit_logbook_event(
        db,
        event=LogbookEventType.MANUAL_ENTRY,
        equipment_id=body["equipment_id"],
        title=body["title"],
        description=body["description"],
        observed_by=user.full_name or user.email,
        source=LogbookEventSource.MANUAL,
        entry_type=body.get("entry_type", "observation"),
        metadata={"manual": True},
    )
    return {"id": entry.id if entry else None, "status": "created"}


# --- History ---

@router.get("/history/{equipment_id}")
async def equipment_history(
    equipment_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    maint = await db.execute(
        select(MaintenanceRecord)
        .where(MaintenanceRecord.equipment_id == equipment_id)
        .order_by(desc(MaintenanceRecord.performed_at))
        .limit(50)
    )
    failures = await db.execute(
        select(FailureHistory)
        .where(FailureHistory.equipment_id == equipment_id)
        .order_by(desc(FailureHistory.occurred_at))
        .limit(50)
    )
    logbook = await db.execute(
        select(LogbookEntry)
        .where(LogbookEntry.equipment_id == equipment_id)
        .order_by(desc(LogbookEntry.created_at))
        .limit(50)
    )
    return {
        "maintenance": [
            {"id": m.id, "type": m.maintenance_type, "description": m.description, "performed_at": m.performed_at, "outcome": m.outcome}
            for m in maint.scalars().all()
        ],
        "failures": [
            {"id": f.id, "failure_type": f.failure_type, "fault_code": f.fault_code, "description": f.description, "occurred_at": f.occurred_at}
            for f in failures.scalars().all()
        ],
        "logbook": [
            {"id": l.id, "entry_type": l.entry_type, "title": l.title, "description": l.description, "created_at": l.created_at}
            for l in logbook.scalars().all()
        ],
    }


# --- Alerts management ---

@router.patch("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    alert = await db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.status = AlertStatus.ACKNOWLEDGED
    await emit_logbook_event(
        db,
        event=LogbookEventType.ALERT_ACKNOWLEDGED,
        equipment_id=alert.equipment_id,
        title=f"Alert acknowledged: {alert.title[:100]}",
        description=alert.message[:1000],
        observed_by="Engineer",
        source=LogbookEventSource.ALERT,
        source_id=alert.id,
    )
    return {"id": alert_id, "status": "acknowledged"}


@router.patch("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    alert = await db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.status = AlertStatus.RESOLVED
    alert.resolved_at = datetime.now(timezone.utc)
    await emit_logbook_event(
        db,
        event=LogbookEventType.ALERT_RESOLVED,
        equipment_id=alert.equipment_id,
        title=f"Alert resolved: {alert.title[:100]}",
        description=alert.message[:1000],
        observed_by="Engineer",
        source=LogbookEventSource.ALERT,
        source_id=alert.id,
    )
    return {"id": alert_id, "status": "resolved"}


# --- Spare parts & procurement ---

@router.get("/spares")
async def list_spares(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(SparePart).order_by(SparePart.quantity_available))
    return [
        {
            "id": s.id,
            "part_number": s.part_number,
            "name": s.name,
            "quantity_available": s.quantity_available,
            "reorder_level": s.reorder_level,
            "lead_time_days": s.lead_time_days,
            "equipment_type": s.equipment_type,
            "unit_cost": s.unit_cost,
        }
        for s in result.scalars().all()
    ]


@router.get("/procurement")
async def list_procurement(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(
        select(ProcurementRequest, SparePart)
        .join(SparePart, ProcurementRequest.spare_part_id == SparePart.id)
        .order_by(desc(ProcurementRequest.requested_at))
    )
    rows = []
    for req, part in result.all():
        rows.append({
            "id": req.id,
            "spare_part_id": req.spare_part_id,
            "part_number": part.part_number,
            "part_name": part.name,
            "equipment_id": req.equipment_id,
            "quantity": req.quantity,
            "urgency": req.urgency,
            "status": req.status,
            "notes": req.notes,
            "requested_at": req.requested_at,
        })
    return rows


@router.post("/procurement")
async def create_procurement(
    body: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    req = ProcurementRequest(
        spare_part_id=body["spare_part_id"],
        equipment_id=body.get("equipment_id"),
        quantity=body.get("quantity", 1),
        urgency=body.get("urgency", "normal"),
        status="pending",
        notes=body.get("notes"),
    )
    db.add(req)
    await db.flush()
    return {"id": req.id, "status": "pending"}


@router.patch("/procurement/{request_id}/approve")
async def approve_procurement(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("supervisor", "admin", "engineer")),
):
    req = await db.get(ProcurementRequest, request_id)
    if not req:
        raise HTTPException(404, "Request not found")
    part = await db.get(SparePart, req.spare_part_id)
    req.status = "approved"
    if part:
        part.quantity_available += req.quantity
    # Log to logbook
    if req.equipment_id:
        db.add(
            LogbookEntry(
                equipment_id=req.equipment_id,
                entry_type="procurement",
                title=f"Spare part order approved — {part.name if part else req.spare_part_id}",
                description=f"Approved by {user.full_name}. Qty: {req.quantity}",
                observed_by=user.full_name,
            )
        )
    await db.flush()
    return {"id": request_id, "status": "approved"}


@router.patch("/procurement/{request_id}/reject")
async def reject_procurement(
    request_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("supervisor", "admin", "engineer")),
):
    req = await db.get(ProcurementRequest, request_id)
    if not req:
        raise HTTPException(404, "Request not found")
    req.status = "rejected"
    req.notes = (req.notes or "") + f" | Rejected by {user.full_name}: {body.get('reason', '')}"
    await db.flush()
    return {"id": request_id, "status": "rejected"}


# --- Production delay logs ---

@router.get("/delay-logs")
async def list_delay_logs(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(DelayLog, Equipment)
        .join(Equipment, DelayLog.equipment_id == Equipment.id)
        .order_by(desc(DelayLog.created_at))
        .limit(50)
    )
    return [
        {
            "id": d.id,
            "equipment_id": d.equipment_id,
            "equipment_code": eq.equipment_code,
            "delay_hours": d.delay_hours,
            "reason": d.reason,
            "fault_code": d.fault_code,
            "severity": d.severity,
            "created_at": d.created_at,
        }
        for d, eq in result.all()
    ]


@router.post("/delay-logs")
async def create_delay_log(
    body: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entry = DelayLog(
        equipment_id=body["equipment_id"],
        delay_hours=float(body.get("delay_hours", 0)),
        reason=body["reason"],
        fault_code=body.get("fault_code"),
        severity=body.get("severity", "medium"),
    )
    db.add(entry)
    await db.flush()
    return {"id": entry.id, "status": "created"}
