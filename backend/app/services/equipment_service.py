from datetime import datetime, timezone

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Alert,
    AlertLevel,
    AlertStatus,
    DelayLog,
    Equipment,
    EquipmentHealthScore,
    FailureHistory,
    MaintenanceRecord,
    Prediction,
    RiskLevel,
    SensorData,
    SparePart,
)
from app.core.fleet import CANONICAL_CODES, CANONICAL_FLEET
from app.schemas import DashboardSummary


def _sensor_reading(sensor: SensorData) -> dict[str, float]:
    return {
        "temperature": sensor.temperature or 0.0,
        "vibration": sensor.vibration or 0.0,
        "pressure": sensor.pressure or 0.0,
        "motor_current": sensor.motor_current or 0.0,
        "health_indicator": sensor.health_indicator,
    }


async def resolve_equipment_health(
    db: AsyncSession, equipment_id: int, sensor: SensorData | None = None
) -> float:
    """Health from latest sensor reading (preferred) or stored score."""
    from app.services.ml.predictive_engine import pm_engine

    if sensor is None:
        sensor = (
            await db.execute(
                select(SensorData)
                .where(SensorData.equipment_id == equipment_id)
                .order_by(desc(SensorData.timestamp))
                .limit(1)
            )
        ).scalar_one_or_none()

    if sensor and sensor.health_indicator is not None:
        reading = _sensor_reading(sensor)
        # Stale DB rows from end-of-life replay should not collapse demo health to 0%
        if sensor.health_indicator < 25:
            from app.services.live_stream import peek_reading

            live = peek_reading(equipment_id)
            reading = {
                "temperature": live["temperature"],
                "vibration": live["vibration"],
                "pressure": live["pressure"],
                "motor_current": live["motor_current"],
                "health_indicator": live["health_indicator"],
            }
        prediction = pm_engine.predict_rul(reading)
        return pm_engine.compute_health_score(reading, prediction)["health_score"]

    stored = await db.scalar(
        select(EquipmentHealthScore.health_score)
        .where(EquipmentHealthScore.equipment_id == equipment_id)
        .order_by(desc(EquipmentHealthScore.computed_at))
        .limit(1)
    )
    return float(stored) if stored is not None else 85.0


async def list_equipment(db: AsyncSession) -> list[Equipment]:
    result = await db.execute(
        select(Equipment)
        .where(Equipment.equipment_code.in_(CANONICAL_CODES))
        .order_by(Equipment.id)
    )
    return list(result.scalars().all())


async def get_equipment(db: AsyncSession, equipment_id: int) -> Equipment | None:
    result = await db.execute(select(Equipment).where(Equipment.id == equipment_id))
    return result.scalar_one_or_none()


async def get_latest_health_scores(db: AsyncSession) -> list[EquipmentHealthScore]:
    subq = (
        select(
            EquipmentHealthScore.equipment_id,
            func.max(EquipmentHealthScore.computed_at).label("max_at"),
        )
        .group_by(EquipmentHealthScore.equipment_id)
        .subquery()
    )
    result = await db.execute(
        select(EquipmentHealthScore)
        .join(
            subq,
            (EquipmentHealthScore.equipment_id == subq.c.equipment_id)
            & (EquipmentHealthScore.computed_at == subq.c.max_at),
        )
        .options(selectinload(EquipmentHealthScore.equipment))
    )
    return list(result.scalars().all())


async def get_dashboard_summary(db: AsyncSession) -> DashboardSummary:
    from app.schemas import AlertResponse

    equipment_list = await list_equipment(db)
    total_equipment = len(equipment_list)
    open_alerts = await db.scalar(
        select(func.count())
        .select_from(Alert)
        .join(Equipment, Alert.equipment_id == Equipment.id)
        .where(Alert.status == AlertStatus.OPEN, Equipment.equipment_code.in_(CANONICAL_CODES))
    ) or 0
    critical_alerts = await db.scalar(
        select(func.count())
        .select_from(Alert)
        .join(Equipment, Alert.equipment_id == Equipment.id)
        .where(
            Alert.status == AlertStatus.OPEN,
            Alert.level == AlertLevel.CRITICAL,
            Equipment.equipment_code.in_(CANONICAL_CODES),
        )
    ) or 0

    health_values: list[float] = []
    high_risk = []
    for eq in equipment_list:
        health = await resolve_equipment_health(db, eq.id)
        health_values.append(health)
        if health < 55:
            high_risk.append(
                {
                    "equipment_id": eq.id,
                    "equipment_code": eq.equipment_code,
                    "name": eq.name,
                    "health_score": round(health, 1),
                    "risk_level": "critical" if health < 45 else "high",
                    "criticality": eq.criticality,
                }
            )

    avg_health = sum(health_values) / len(health_values) if health_values else 100.0

    recent_result = await db.execute(
        select(Alert).order_by(desc(Alert.created_at)).limit(5)
    )
    recent_alerts = [
        AlertResponse.model_validate(a) for a in recent_result.scalars().all()
    ]

    bottleneck_equipment = sorted(
        high_risk,
        key=lambda x: (x["health_score"], -x.get("criticality", 0)),
    )[:5]

    delay_result = await db.execute(
        select(DelayLog, Equipment)
        .join(Equipment, DelayLog.equipment_id == Equipment.id)
        .order_by(desc(DelayLog.created_at))
        .limit(10)
    )
    recent_delay_logs = [
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
        for d, eq in delay_result.all()
    ]

    # Boost bottleneck ranking with recent production delays
    delay_by_eq = {}
    for log in recent_delay_logs:
        delay_by_eq[log["equipment_id"]] = delay_by_eq.get(log["equipment_id"], 0) + log["delay_hours"]
    if delay_by_eq:
        enriched = []
        for item in high_risk:
            eq_id = item["equipment_id"]
            enriched.append({**item, "delay_hours": delay_by_eq.get(eq_id, 0)})
        bottleneck_equipment = sorted(
            enriched,
            key=lambda x: (x["health_score"], -x.get("delay_hours", 0)),
        )[:5]

    early_warnings = []
    pred_result = await db.execute(
        select(Prediction, Equipment)
        .join(Equipment, Prediction.equipment_id == Equipment.id)
        .where(Equipment.equipment_code.in_(CANONICAL_CODES))
        .order_by(desc(Prediction.created_at))
        .limit(20)
    )
    seen = set()
    for pred, eq in pred_result.all():
        if pred.equipment_id in seen:
            continue
        seen.add(pred.equipment_id)
        if pred.remaining_useful_life_hours and pred.remaining_useful_life_hours < 48:
            early_warnings.append({
                "equipment_id": eq.id,
                "equipment_code": eq.equipment_code,
                "name": eq.name,
                "rul_hours": pred.remaining_useful_life_hours,
                "failure_probability": pred.failure_probability,
                "risk_level": pred.risk_level.value if hasattr(pred.risk_level, "value") else str(pred.risk_level),
                "message": f"RUL below 48h — schedule intervention before catastrophic failure",
            })
        elif pred.failure_probability > 0.65:
            early_warnings.append({
                "equipment_id": eq.id,
                "equipment_code": eq.equipment_code,
                "name": eq.name,
                "rul_hours": pred.remaining_useful_life_hours,
                "failure_probability": pred.failure_probability,
                "risk_level": pred.risk_level.value if hasattr(pred.risk_level, "value") else str(pred.risk_level),
                "message": "Elevated failure probability detected from C-MAPSS-calibrated sensors",
            })

    return DashboardSummary(
        total_equipment=total_equipment,
        open_alerts=open_alerts,
        critical_alerts=critical_alerts,
        avg_health_score=round(avg_health, 2),
        high_risk_equipment=high_risk,
        recent_alerts=recent_alerts,
        bottleneck_equipment=bottleneck_equipment,
        early_warnings=early_warnings[:5],
        recent_delay_logs=recent_delay_logs,
        data_sources={
            "sensors": "NASA C-MAPSS FD001 (simulated plant IoT)",
            "knowledge": "Manuals, SOPs, failure reports (RAG/Qdrant)",
            "ml": "Isolation Forest + XGBoost RUL",
        },
    )


async def get_plant_twin(db: AsyncSession) -> dict:
    """Five C-MAPSS FD001 engine units mapped 1:1 to canonical steel plant assets."""
    from app.models import Alert, AlertStatus

    health_scores = [h for h in await get_latest_health_scores(db) if h.equipment.equipment_code in CANONICAL_CODES]
    health_by_id = {h.equipment_id: h for h in health_scores}
    equipment_list = await list_equipment(db)

    open_alerts = await db.execute(
        select(Alert.equipment_id, func.count())
        .where(Alert.status == AlertStatus.OPEN)
        .group_by(Alert.equipment_id)
    )
    alert_counts = {row[0]: row[1] for row in open_alerts.all()}

    assets = []
    for eq in equipment_list:
        meta = eq.metadata_json or {}
        cmapss_unit = meta.get("cmapss_unit") or next(
            (a["cmapss_unit"] for a in CANONICAL_FLEET if a["code"] == eq.equipment_code), None
        )
        h = health_by_id.get(eq.id)
        health = await resolve_equipment_health(db, eq.id)
        risk = h.risk_level.value if h and hasattr(h.risk_level, "value") else (
            "critical" if health < 45 else "high" if health < 65 else "medium" if health < 80 else "low"
        )
        alerts = alert_counts.get(eq.id, 0)
        pred = await get_latest_predictions(db, eq.id)
        assets.append({
            "id": eq.id,
            "equipment_code": eq.equipment_code,
            "name": eq.name,
            "location": eq.location,
            "equipment_type": eq.equipment_type,
            "cmapss_unit": cmapss_unit,
            "cmapss_dataset": "FD001",
            "health_score": round(health, 1),
            "rul_hours": pred.remaining_useful_life_hours if pred else None,
            "failure_probability": pred.failure_probability if pred else None,
            "risk_level": risk,
            "criticality": eq.criticality,
            "alerts": alerts,
            "status": "critical" if health < 45 else "degraded" if health < 65 else "healthy",
        })

    healthy = len([a for a in assets if a["status"] == "healthy"])
    warning = len([a for a in assets if a["status"] == "degraded"])
    critical = len([a for a in assets if a["status"] == "critical"])
    avg = sum(a["health_score"] for a in assets) / max(len(assets), 1)

    return {
        "cmapss_fleet": assets,
        "assets": assets,
        "summary": {
            "total": len(assets),
            "healthy": healthy,
            "warning": warning,
            "critical": critical,
            "avg_health": round(avg, 1),
            "open_alerts": sum(alert_counts.get(a["id"], 0) for a in assets),
        },
        "dataset": {
            "name": "NASA C-MAPSS FD001",
            "description": "5 turbofan engine degradation trajectories mapped to steel plant equipment",
            "units": 5,
        },
    }


async def get_plant_priority(db: AsyncSession) -> list[dict]:
    """Bottleneck prioritization — composite score from criticality, alerts, RUL, spares."""
    from app.services.live_stream import peek_reading
    from app.services.ml.predictive_engine import pm_engine, risk_engine
    from app.services.procurement_risk import spare_procurement_profile

    health_scores = [h for h in await get_latest_health_scores(db) if h.equipment.equipment_code in CANONICAL_CODES]
    health_by_id = {h.equipment_id: h for h in health_scores}

    equipment_list = await list_equipment(db)
    priority_list = []

    for eq in equipment_list:
        meta = eq.metadata_json or {}
        location = eq.location
        cmapss_unit = meta.get("cmapss_unit") or next(
            (a["cmapss_unit"] for a in CANONICAL_FLEET if a["code"] == eq.equipment_code), None
        )
        h = health_by_id.get(eq.id)

        health = await resolve_equipment_health(db, eq.id)

        alert_res = await db.execute(
            select(Alert).where(
                Alert.equipment_id == eq.id,
                Alert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]),
            )
        )
        alerts = list(alert_res.scalars().all())
        critical_alerts = sum(1 for a in alerts if a.level == AlertLevel.CRITICAL)
        high_alerts = sum(1 for a in alerts if a.level == AlertLevel.HIGH)

        pred = await get_latest_predictions(db, eq.id)

        live = peek_reading(eq.id)
        live_reading = {
            "temperature": live["temperature"],
            "vibration": live["vibration"],
            "pressure": live["pressure"],
            "motor_current": live["motor_current"],
            "health_indicator": live["health_indicator"],
        }
        live_pred = pm_engine.predict_rul(live_reading)
        rul_hours = live_pred.get("remaining_useful_life_hours") or live.get("rul_hours")
        if rul_hours is None and pred:
            rul_hours = pred.remaining_useful_life_hours
        rul_days = (rul_hours / 24) if rul_hours is not None else None

        crit_score = min(eq.criticality, 5)

        delay_res = await db.execute(
            select(DelayLog).where(DelayLog.equipment_id == eq.id).order_by(desc(DelayLog.created_at)).limit(5)
        )
        recent_delays = list(delay_res.scalars().all())
        delay_hours_sum = sum(d.delay_hours for d in recent_delays)

        spare_res = await db.execute(
            select(SparePart).where(SparePart.equipment_type == eq.equipment_type)
        )
        spares = list(spare_res.scalars().all())
        spare_rows = [
            {
                "part_number": s.part_number,
                "name": s.name,
                "quantity_available": s.quantity_available,
                "reorder_level": s.reorder_level,
                "lead_time_days": s.lead_time_days,
            }
            for s in spares
        ]
        profile = spare_procurement_profile(spare_rows)
        spares_ok = profile["spare_stock"] > profile["reorder_level"]

        risk_assessment = risk_engine.compute(
            criticality=eq.criticality,
            failure_probability=float(live_pred.get("failure_probability") or 0.5),
            downtime_cost=float(meta.get("downtime_cost", 50000)),
            spare_availability=profile["spare_stock"],
            lead_time_days=profile["lead_time_days"],
            rul_hours=float(rul_hours) if rul_hours is not None else None,
            reorder_level=profile["reorder_level"],
        )
        risk_level = risk_assessment["risk_level"]
        if hasattr(risk_level, "value"):
            risk_level = risk_level.value

        priority_score = (
            crit_score * 10
            + critical_alerts * 30
            + high_alerts * 15
            + min(25, int(delay_hours_sum * 8))
            + (25 if rul_days is not None and rul_days < 3 else 0)
            + (15 if rul_days is not None and rul_days < 7 else 0)
            + (20 if str(risk_level).lower() == "critical" else 10 if str(risk_level).lower() == "high" else 0)
            + (0 if spares_ok else 15)
            + (35 if risk_assessment["procurement_risk"] == "critical" else 20 if risk_assessment["procurement_risk"] == "high" else 0)
        )

        maint_res = await db.execute(
            select(MaintenanceRecord)
            .where(MaintenanceRecord.equipment_id == eq.id)
            .order_by(desc(MaintenanceRecord.performed_at))
            .limit(1)
        )
        last_maint = maint_res.scalar_one_or_none()
        days_since_maint = None
        if last_maint and last_maint.performed_at:
            performed_at = last_maint.performed_at
            # SQLite returns naive datetimes; Postgres returns tz-aware ones.
            # Normalize to UTC-aware so the subtraction never crashes.
            if performed_at.tzinfo is None:
                performed_at = performed_at.replace(tzinfo=timezone.utc)
            days_since_maint = (datetime.now(timezone.utc) - performed_at).days

        if risk_assessment["procurement_risk"] == "critical" or (critical_alerts > 0 and str(risk_level).lower() == "critical"):
            action = "IMMEDIATE SHUTDOWN & REPAIR"
        elif critical_alerts > 0 or (rul_days is not None and rul_days < 3) or risk_assessment["procurement_risk"] == "critical":
            action = "URGENT: Schedule within 24h"
        elif high_alerts > 0 or (rul_days is not None and rul_days < 7) or risk_assessment["procurement_risk"] == "high":
            action = "PLAN: Schedule within 1 week"
        else:
            action = "MONITOR: Normal operations"

        priority_list.append({
            "equipment_id": eq.id,
            "equipment_code": eq.equipment_code,
            "equipment_name": eq.name,
            "name": eq.name,
            "equipment_type": eq.equipment_type,
            "plant_area": location,
            "sector": location,
            "location": location,
            "cmapss_unit": cmapss_unit,
            "criticality": eq.criticality,
            "priority_score": priority_score,
            "health_score": round(health, 1),
            "active_alerts": len(alerts),
            "critical_alerts": critical_alerts,
            "risk_level": str(risk_level).lower(),
            "rul_days": round(rul_days, 1) if rul_days is not None else None,
            "rul_hours": round(rul_hours, 1) if rul_hours is not None else None,
            "days_since_maintenance": days_since_maint,
            "critical_spares_available": spares_ok,
            "spare_stock": profile["spare_stock"],
            "lead_time_days": profile["lead_time_days"],
            "critical_spare_part": profile["critical_part_number"],
            "critical_spare_name": profile["critical_part_name"],
            "procurement_risk": risk_assessment["procurement_risk"],
            "business_impact_inr": risk_assessment["business_impact_inr"],
            "risk_escalated": risk_assessment["escalated"],
            "escalation_reason": risk_assessment["escalation_reason"],
            "recent_delay_hours": round(delay_hours_sum, 1),
            "recommended_action": action,
        })

    priority_list.sort(key=lambda x: x["priority_score"], reverse=True)
    return priority_list


async def ingest_sensor_reading(db: AsyncSession, equipment_id: int, data: dict) -> SensorData:
    sensor_fields = ("temperature", "vibration", "pressure", "motor_current", "health_indicator")
    payload = {k: data[k] for k in sensor_fields if k in data}
    raw_data = {
        k: v
        for k, v in data.items()
        if k not in sensor_fields and k not in ("equipment_id", "timestamp", "source")
    }
    reading = SensorData(
        equipment_id=equipment_id,
        timestamp=datetime.now(timezone.utc),
        raw_data=raw_data or None,
        **payload,
    )
    db.add(reading)
    await db.flush()
    return reading


async def list_spare_parts(db: AsyncSession) -> list[SparePart]:
    result = await db.execute(select(SparePart).order_by(SparePart.quantity_available))
    return list(result.scalars().all())


async def get_failure_history(db: AsyncSession, equipment_id: int) -> list[FailureHistory]:
    result = await db.execute(
        select(FailureHistory)
        .where(FailureHistory.equipment_id == equipment_id)
        .order_by(desc(FailureHistory.occurred_at))
    )
    return list(result.scalars().all())


async def get_maintenance_history(db: AsyncSession, equipment_id: int) -> list[MaintenanceRecord]:
    result = await db.execute(
        select(MaintenanceRecord)
        .where(MaintenanceRecord.equipment_id == equipment_id)
        .order_by(desc(MaintenanceRecord.performed_at))
    )
    return list(result.scalars().all())


async def get_latest_predictions(db: AsyncSession, equipment_id: int) -> Prediction | None:
    result = await db.execute(
        select(Prediction)
        .where(Prediction.equipment_id == equipment_id)
        .order_by(desc(Prediction.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()
