from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, AlertLevel, AlertStatus, AnomalyEvent, NotificationHistory, RiskLevel, Role, User
from app.core.logbook_events import LogbookEventSource, LogbookEventType
from app.services.logbook_service import emit_logbook_event
from app.services.ml.predictive_engine import pm_engine

ALERT_COOLDOWN_MINUTES = 30
MAX_OPEN_ALERTS_PER_EQUIPMENT = 3


def _map_alert_level(level: str) -> AlertLevel:
    mapping = {
        "info": AlertLevel.INFO,
        "warning": AlertLevel.WARNING,
        "high": AlertLevel.HIGH,
        "critical": AlertLevel.CRITICAL,
    }
    return mapping.get(level.lower(), AlertLevel.WARNING)


async def create_alert(
    db: AsyncSession,
    *,
    equipment_id: int,
    title: str,
    message: str,
    level: str,
    source: str,
    risk_level: RiskLevel | None = None,
    metadata: dict | None = None,
) -> Alert:
    alert = Alert(
        equipment_id=equipment_id,
        title=title,
        message=message,
        level=_map_alert_level(level),
        source=source,
        status=AlertStatus.OPEN,
        risk_level=risk_level,
        metadata_json=metadata or {},
        created_at=datetime.now(timezone.utc),
    )
    db.add(alert)
    await db.flush()
    await emit_logbook_event(
        db,
        event=LogbookEventType.ALERT_CREATED,
        equipment_id=equipment_id,
        title=f"Alert: {title[:120]}",
        description=message[:1500],
        observed_by="Alert Engine",
        source=LogbookEventSource.ALERT,
        source_id=alert.id,
        metadata={"level": level, "risk_level": risk_level.value if risk_level else None},
    )
    return alert


async def notify_users(db: AsyncSession, alert: Alert, user_ids: list[int] | None = None) -> None:
    for user_id in user_ids or []:
        db.add(
            NotificationHistory(
                user_id=user_id,
                alert_id=alert.id,
                channel="in_app",
                message=f"[{alert.level.value.upper()}] {alert.title}: {alert.message[:200]}",
            )
        )


async def notify_roles(db: AsyncSession, alert: Alert, role_names: list[str]) -> None:
    """Route in-app notifications to users with given roles (e.g. supervisor on critical alerts)."""
    if not role_names:
        return
    result = await db.execute(
        select(User.id)
        .join(Role, User.role_id == Role.id)
        .where(Role.name.in_(role_names), User.is_active.is_(True))
    )
    user_ids = [row[0] for row in result.all()]
    await notify_users(db, alert, user_ids)


def _evaluate_alert(reading: dict, prediction: dict, anomaly: dict) -> tuple[bool, str]:
    temp = reading.get("temperature") or 0
    vib = reading.get("vibration") or 0
    health = reading.get("health_indicator") or 100
    failure_prob = prediction.get("failure_probability") or 0
    rul = prediction.get("remaining_useful_life_hours") or 999

    if temp > 105 or vib > 8.5 or failure_prob > 0.75 or rul < 24 or health < 35:
        return True, "critical"
    if temp > 92 or vib > 6.0 or failure_prob > 0.5 or rul < 72 or health < 55 or anomaly["is_anomaly"]:
        return True, "high"
    if temp > 85 or vib > 4.5 or failure_prob > 0.35 or health < 70:
        return True, "warning"
    return False, "info"


async def prune_alert_backlog(db: AsyncSession, max_per_equipment: int = MAX_OPEN_ALERTS_PER_EQUIPMENT) -> int:
    """Resolve duplicate open alerts — keeps demo readable (not 100+ from live monitor)."""
    from app.models import Equipment

    resolved = 0
    eq_result = await db.execute(select(Equipment.id))
    for (eq_id,) in eq_result.all():
        open_res = await db.execute(
            select(Alert)
            .where(Alert.equipment_id == eq_id, Alert.status == AlertStatus.OPEN)
            .order_by(desc(Alert.created_at))
        )
        alerts = list(open_res.scalars().all())
        for extra in alerts[max_per_equipment:]:
            extra.status = AlertStatus.RESOLVED
            extra.resolved_at = datetime.now(timezone.utc)
            resolved += 1
    return resolved


async def process_sensor_and_alert(db: AsyncSession, equipment_id: int, reading: dict) -> dict:
    anomaly = pm_engine.detect_anomaly(reading)
    prediction = pm_engine.predict_rul(reading)
    alert = None

    if anomaly.get("is_anomaly"):
        db.add(
            AnomalyEvent(
                equipment_id=equipment_id,
                sensor_type="multivariate",
                anomaly_score=float(anomaly.get("anomaly_score", anomaly.get("score", 0))),
                threshold=float(anomaly.get("threshold", 0.5)),
                detected_at=datetime.now(timezone.utc),
                details={
                    "temperature": reading.get("temperature"),
                    "vibration": reading.get("vibration"),
                    "source": reading.get("source", "live_monitor"),
                },
            )
        )
        await db.flush()

    should_alert, level = _evaluate_alert(reading, prediction, anomaly)

    if should_alert and level in ("critical", "high", "warning"):
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=ALERT_COOLDOWN_MINUTES)
        titles = {
            "critical": "CRITICAL — Catastrophic failure risk",
            "high": "HIGH — Abnormal sensor signature",
            "warning": "WARNING — Degradation trend detected",
        }
        title = titles.get(level, "Sensor alert")
        message = (
            f"Temp {reading.get('temperature', 0):.1f}°C · "
            f"Vibration {reading.get('vibration', 0):.2f} mm/s · "
            f"Health {reading.get('health_indicator', 0):.0f}% · "
            f"RUL {prediction.get('remaining_useful_life_hours', 0):.0f}h · "
            f"Failure prob {prediction.get('failure_probability', 0):.0%}"
        )

        recent = await db.execute(
            select(Alert)
            .where(
                Alert.equipment_id == equipment_id,
                Alert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]),
                Alert.level == _map_alert_level(level),
                Alert.created_at >= cutoff,
            )
            .order_by(desc(Alert.created_at))
            .limit(1)
        )
        existing = recent.scalar_one_or_none()
        if existing:
            existing.message = message
            existing.metadata_json = {"anomaly": anomaly, "prediction": prediction, "reading": reading}
            alert = existing
        else:
            alert = await create_alert(
                db,
                equipment_id=equipment_id,
                title=title,
                message=message,
                level=level,
                source="live_monitor",
                risk_level=prediction["risk_level"],
                metadata={"anomaly": anomaly, "prediction": prediction, "reading": reading},
            )
            if level in ("critical", "high"):
                await notify_roles(db, alert, ["supervisor", "admin"])

    pred = prediction
    risk = pred.get("risk_level")
    risk_str = risk.value if hasattr(risk, "value") else str(risk)

    return {
        "anomaly": anomaly,
        "prediction": prediction,
        "alert_id": alert.id if alert else None,
        "risk_level": risk_str.replace("RiskLevel.", "").lower(),
        "failure_probability": pred.get("failure_probability"),
        "remaining_useful_life_hours": pred.get("remaining_useful_life_hours"),
    }


async def ensure_demo_alerts(db: AsyncSession) -> int:
    """Seed realistic open alerts if fleet has too few active alerts for demo."""
    from sqlalchemy import func
    from app.models import Equipment

    open_count = await db.scalar(
        select(func.count()).select_from(Alert).where(Alert.status == AlertStatus.OPEN)
    ) or 0
    if open_count >= 5:
        return 0

    eq_result = await db.execute(select(Equipment).order_by(Equipment.criticality.desc()))
    equipment_list = list(eq_result.scalars().all())
    demos = [
        ("RM-002", "critical", "Rolling Mill Motor — bearing vibration exceedance",
         "Vibration 9.2 mm/s (>limit 6.0). Temperature 108°C. Fault E-2041. RUL ~18h. Immediate bearing inspection required."),
        ("BF-001", "high", "Blast Furnace Blower — thermal drift",
         "Temperature 96°C trending up. Pressure variance detected. Schedule inspection within 24h."),
        ("CP-003", "high", "Coke Oven Compressor — pressure anomaly",
         "Discharge pressure 138 bar approaching upper limit. Check valve assembly."),
        ("CN-005", "warning", "Caster Drive — motor current spike",
         "Motor current 78A intermittent spikes. Monitor lubrication system."),
        ("CW-004", "warning", "Cooling Water Pump — low health index",
         "Health score 52%. RUL estimate 48h. Plan preventive maintenance."),
    ]
    created = 0
    code_map = {e.equipment_code: e for e in equipment_list}
    for code, level, title, msg in demos:
        eq = code_map.get(code)
        if not eq:
            continue
        exists = await db.scalar(
            select(func.count()).select_from(Alert).where(
                Alert.equipment_id == eq.id,
                Alert.status == AlertStatus.OPEN,
                Alert.title == title,
            )
        )
        if exists:
            continue
        await create_alert(
            db, equipment_id=eq.id, title=title, message=msg,
            level=level, source="predictive_maintenance",
        )
        created += 1
    return created
