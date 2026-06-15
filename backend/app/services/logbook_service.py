"""Central auto-logbook — event-driven maintenance history."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logbook_events import (
    AUTO_EVENT_SOURCES,
    EVENT_ENTRY_TYPE,
    LogbookEventSource,
    LogbookEventType,
)
from app.models import Equipment, LogbookEntry


def _entry_type_for(event: LogbookEventType, override: str | None = None) -> str:
    if override:
        return override
    return EVENT_ENTRY_TYPE.get(event, "observation")


async def has_recent_logbook_event(
    db: AsyncSession,
    *,
    equipment_id: int,
    source_event: LogbookEventType | str,
    dedupe_key: str | None = None,
    within_hours: int = 24,
) -> bool:
    """Prevent duplicate auto-entries for the same event within a time window."""
    since = datetime.now(timezone.utc) - timedelta(hours=within_hours)
    q = (
        select(func.count())
        .select_from(LogbookEntry)
        .where(
            LogbookEntry.equipment_id == equipment_id,
            LogbookEntry.source_event == str(source_event),
            LogbookEntry.created_at >= since,
        )
    )
    if dedupe_key:
        # JSON path filter varies by DB; scan recent rows for small fleets
        recent = await db.execute(
            select(LogbookEntry.metadata_json)
            .where(
                LogbookEntry.equipment_id == equipment_id,
                LogbookEntry.source_event == str(source_event),
                LogbookEntry.created_at >= since,
            )
            .limit(20)
        )
        for meta in recent.scalars().all():
            if (meta or {}).get("dedupe_key") == dedupe_key:
                return True
        return False
    return (await db.scalar(q) or 0) > 0


async def emit_logbook_event(
    db: AsyncSession,
    *,
    event: LogbookEventType,
    equipment_id: int | None,
    title: str,
    description: str,
    observed_by: str = "System",
    source: LogbookEventSource | str | None = None,
    source_id: int | None = None,
    entry_type: str | None = None,
    metadata: dict | None = None,
    dedupe_key: str | None = None,
    dedupe_hours: int = 24,
) -> LogbookEntry | None:
    """Primary event dispatcher — all auto-logbook flows go through here."""
    if not equipment_id:
        return None

    if event in AUTO_EVENT_SOURCES and dedupe_key is not None:
        if await has_recent_logbook_event(
            db,
            equipment_id=equipment_id,
            source_event=event,
            dedupe_key=dedupe_key,
            within_hours=dedupe_hours,
        ):
            return None

    meta = dict(metadata or {})
    src = str(source) if source else None
    if src:
        meta["source"] = src
    if source_id is not None:
        meta["source_id"] = source_id
    if dedupe_key:
        meta["dedupe_key"] = dedupe_key
    is_auto = event in AUTO_EVENT_SOURCES and not meta.get("manual")
    meta["auto_generated"] = is_auto
    meta["recorded_at"] = datetime.now(timezone.utc).isoformat()
    meta["event_type"] = str(event)

    entry = LogbookEntry(
        equipment_id=equipment_id,
        entry_type=_entry_type_for(event, entry_type),
        title=title[:255],
        description=description[:4000],
        observed_by=observed_by,
        source_event=str(event),
        source_id=source_id,
        auto_generated=is_auto,
        metadata_json=meta,
    )
    db.add(entry)
    await db.flush()
    return entry


async def record_logbook_event(
    db: AsyncSession,
    *,
    equipment_id: int | None,
    entry_type: str,
    title: str,
    description: str,
    observed_by: str = "System",
    source: str | None = None,
    source_id: int | None = None,
    metadata: dict | None = None,
) -> LogbookEntry | None:
    """Backward-compatible wrapper — maps legacy calls to typed events."""
    event_map = {
        "alert": LogbookEventType.ALERT_CREATED,
        "diagnosis": LogbookEventType.DIAGNOSIS_COMPLETED,
        "report": LogbookEventType.REPORT_GENERATED,
        "feedback": LogbookEventType.FEEDBACK_SUBMITTED,
        "ai_analysis": LogbookEventType.AI_ANALYSIS,
        "reminder": LogbookEventType.MAINTENANCE_SCHEDULED,
        "schedule": LogbookEventType.MAINTENANCE_SCHEDULED,
    }
    event = event_map.get(entry_type, LogbookEventType.MANUAL_ENTRY)
    source_enum = None
    if source:
        try:
            source_enum = LogbookEventSource(source)
        except ValueError:
            source_enum = LogbookEventSource.SYSTEM

    return await emit_logbook_event(
        db,
        event=event,
        equipment_id=equipment_id,
        title=title,
        description=description,
        observed_by=observed_by,
        source=source_enum,
        source_id=source_id,
        entry_type=entry_type,
        metadata=metadata,
        dedupe_key=None,
    )


async def sync_maintenance_schedule_logbook(db: AsyncSession, tasks: list[dict]) -> int:
    """Auto-log critical/high scheduler tasks — deduped per asset per day."""
    logged = 0
    for task in tasks:
        if task.get("urgency") not in ("critical", "high"):
            continue
        equipment_id = task.get("id") or task.get("equipment_id")
        if not equipment_id:
            continue
        start = (task.get("start") or "")[:10]
        dedupe_key = f"{equipment_id}:{start}:{task.get('urgency')}"
        entry = await emit_logbook_event(
            db,
            event=LogbookEventType.MAINTENANCE_SCHEDULED,
            equipment_id=equipment_id,
            title=f"Maintenance scheduled — {task.get('equipment_code', 'Asset')}",
            description=(
                f"Task: {task.get('task', 'Inspection')}\n"
                f"Urgency: {task.get('urgency', 'planned').upper()}\n"
                f"Window: {task.get('start', 'TBD')} → {task.get('end', 'TBD')}\n"
                f"Health: {task.get('health_score', 'N/A')}% · RUL: {task.get('rul_days', 'N/A')} days"
            )[:1500],
            observed_by="Maintenance Scheduler",
            source=LogbookEventSource.SCHEDULER,
            entry_type="schedule",
            metadata={
                "urgency": task.get("urgency"),
                "start": task.get("start"),
                "end": task.get("end"),
                "duration_hours": task.get("duration_hours"),
                "auto_schedule": True,
            },
            dedupe_key=dedupe_key,
            dedupe_hours=24,
        )
        if entry:
            logged += 1
    return logged


def serialize_logbook_entry(entry: LogbookEntry, equipment_code: str | None = None) -> dict:
    meta = entry.metadata_json or {}
    auto = entry.auto_generated if entry.auto_generated else bool(meta.get("auto_generated"))
    return {
        "id": entry.id,
        "equipment_id": entry.equipment_id,
        "equipment_code": equipment_code or f"#{entry.equipment_id}",
        "entry_type": entry.entry_type,
        "source_event": entry.source_event or meta.get("event_type"),
        "title": entry.title,
        "description": entry.description,
        "observed_by": entry.observed_by,
        "auto_generated": auto,
        "source_id": entry.source_id or meta.get("source_id"),
        "metadata_json": meta,
        "created_at": entry.created_at,
    }


async def get_logbook_summary(db: AsyncSession, equipment_id: int | None = None) -> dict:
    def _apply(q):
        if equipment_id:
            return q.where(LogbookEntry.equipment_id == equipment_id)
        return q

    total = await db.scalar(_apply(select(func.count()).select_from(LogbookEntry))) or 0
    # Count auto entries: column OR legacy metadata flag
    auto_q = _apply(select(LogbookEntry))
    auto_rows = list((await db.execute(auto_q)).scalars().all())
    auto = sum(
        1
        for e in auto_rows
        if e.auto_generated or (e.metadata_json or {}).get("auto_generated")
    )

    type_q = _apply(select(LogbookEntry.entry_type, func.count()).group_by(LogbookEntry.entry_type))
    by_type = {row[0]: row[1] for row in (await db.execute(type_q)).all()}

    event_q = _apply(
        select(LogbookEntry.source_event, func.count())
        .where(LogbookEntry.source_event.isnot(None))
        .group_by(LogbookEntry.source_event)
    )
    by_event = {row[0]: row[1] for row in (await db.execute(event_q)).all()}

    recent_q = _apply(select(LogbookEntry).order_by(desc(LogbookEntry.created_at)).limit(5))
    recent_rows = list((await db.execute(recent_q)).scalars().all())
    eq_map = await _equipment_code_map(db)

    return {
        "total_entries": total,
        "auto_generated": auto,
        "manual_entries": max(0, total - auto),
        "by_type": by_type,
        "by_event": by_event,
        "coverage_pct": round((auto / total) * 100, 1) if total else 0.0,
        "recent": [serialize_logbook_entry(e, eq_map.get(e.equipment_id)) for e in recent_rows],
    }


async def get_equipment_timeline(db: AsyncSession, equipment_id: int, limit: int = 50) -> list[dict]:
    eq = await db.get(Equipment, equipment_id)
    if not eq:
        return []
    result = await db.execute(
        select(LogbookEntry)
        .where(LogbookEntry.equipment_id == equipment_id)
        .order_by(desc(LogbookEntry.created_at))
        .limit(limit)
    )
    entries = list(result.scalars().all())
    return [serialize_logbook_entry(e, eq.equipment_code) for e in entries]


async def _equipment_code_map(db: AsyncSession) -> dict[int, str]:
    result = await db.execute(select(Equipment.id, Equipment.equipment_code))
    return {row[0]: row[1] for row in result.all()}
