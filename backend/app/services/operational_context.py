"""Load operational inputs required by hackathon problem statement §4.1–4.3."""

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, AlertStatus, DelayLog, Equipment, FailureHistory, LogbookEntry, MaintenanceRecord


async def load_operational_context(db: AsyncSession, equipment_id: int | None) -> dict:
    if not equipment_id:
        return {}

    eq = await db.scalar(select(Equipment).where(Equipment.id == equipment_id))
    if not eq:
        return {}

    delay_rows = list(
        (
            await db.execute(
                select(DelayLog)
                .where(DelayLog.equipment_id == equipment_id)
                .order_by(desc(DelayLog.created_at))
                .limit(8)
            )
        ).scalars()
    )
    failures = list(
        (
            await db.execute(
                select(FailureHistory)
                .where(FailureHistory.equipment_id == equipment_id)
                .order_by(desc(FailureHistory.occurred_at))
                .limit(5)
            )
        ).scalars()
    )
    maintenance = list(
        (
            await db.execute(
                select(MaintenanceRecord)
                .where(MaintenanceRecord.equipment_id == equipment_id)
                .order_by(desc(MaintenanceRecord.performed_at))
                .limit(5)
            )
        ).scalars()
    )
    logbook = list(
        (
            await db.execute(
                select(LogbookEntry)
                .where(LogbookEntry.equipment_id == equipment_id)
                .order_by(desc(LogbookEntry.created_at))
                .limit(5)
            )
        ).scalars()
    )
    alerts = list(
        (
            await db.execute(
                select(Alert)
                .where(
                    Alert.equipment_id == equipment_id,
                    Alert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]),
                )
                .order_by(desc(Alert.created_at))
                .limit(6)
            )
        ).scalars()
    )

    total_delay_h = sum(d.delay_hours for d in delay_rows)

    return {
        "equipment_code": eq.equipment_code,
        "delay_logs": [
            {
                "delay_hours": d.delay_hours,
                "fault_code": d.fault_code,
                "reason": d.reason,
                "severity": d.severity,
                "when": d.created_at.isoformat() if d.created_at else None,
            }
            for d in delay_rows
        ],
        "failure_incidents": [
            {
                "fault_code": f.fault_code,
                "failure_type": f.failure_type,
                "description": f.description,
                "root_cause": f.root_cause,
                "downtime_hours": f.downtime_hours,
                "resolution": f.resolution,
            }
            for f in failures
        ],
        "maintenance_history": [
            {
                "type": m.maintenance_type,
                "description": m.description,
                "performed_by": m.performed_by,
                "outcome": m.outcome,
            }
            for m in maintenance
        ],
        "logbook_entries": [
            {"type": l.entry_type, "title": l.title, "description": l.description[:300]}
            for l in logbook
        ],
        "open_fault_alerts": [
            {
                "title": a.title,
                "message": a.message,
                "level": a.level.value if hasattr(a.level, "value") else str(a.level),
                "source": a.source,
            }
            for a in alerts
        ],
        "total_recent_delay_hours": round(total_delay_h, 1),
    }
