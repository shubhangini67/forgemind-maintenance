"""Application bootstrap: seed data, train models, run batch predictions."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import desc, func, select, text

from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal, engine
from app.models import (
    Alert,
    AlertLevel,
    AlertStatus,
    Base,
    Equipment,
    EquipmentHealthScore,
    Prediction,
    SensorData,
)
from app.services.alerts.alert_engine import create_alert, ensure_demo_alerts
from app.services.ml.predictive_engine import get_pm_engine

logger = get_logger(__name__)

_FEEDBACK_COLUMNS = [
    ("query", "TEXT"),
    ("recommendation", "TEXT"),
    ("source_type", "VARCHAR(50)"),
    ("fault_type", "VARCHAR(100)"),
    ("report_id", "INTEGER"),
]


async def _ensure_feedback_columns(conn) -> None:
    """Add feedback learning columns on existing databases (SQLite / Postgres)."""
    dialect = conn.dialect.name
    for col_name, col_type in _FEEDBACK_COLUMNS:
        try:
            if dialect == "sqlite":
                await conn.execute(text(f"ALTER TABLE feedback ADD COLUMN {col_name} {col_type}"))
            else:
                await conn.execute(
                    text(f"ALTER TABLE feedback ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
                )
        except Exception:
            pass


async def run_batch_predictions(db) -> int:
    """Run ML on latest sensor reading for every equipment."""
    engine_ml = get_pm_engine()
    result = await db.execute(select(Equipment))
    equipment_list = list(result.scalars().all())
    count = 0

    for eq in equipment_list:
        sensor_result = await db.execute(
            select(SensorData)
            .where(SensorData.equipment_id == eq.id)
            .order_by(desc(SensorData.timestamp))
            .limit(1)
        )
        latest = sensor_result.scalar_one_or_none()
        if not latest:
            continue

        reading = {
            "temperature": latest.temperature,
            "vibration": latest.vibration,
            "pressure": latest.pressure,
            "motor_current": latest.motor_current,
            "health_indicator": latest.health_indicator,
        }
        prediction = engine_ml.predict_rul(reading)
        health = engine_ml.compute_health_score(reading, prediction)

        db.add(
            Prediction(
                equipment_id=eq.id,
                failure_probability=prediction["failure_probability"],
                degradation_score=prediction["degradation_score"],
                remaining_useful_life_hours=prediction["remaining_useful_life_hours"],
                risk_level=prediction["risk_level"],
                model_version=prediction["model_version"],
                features_used=prediction["features_used"],
                explanation=prediction["explanation"],
            )
        )
        db.add(
            EquipmentHealthScore(
                equipment_id=eq.id,
                health_score=health["health_score"],
                degradation_trend=health["degradation_trend"],
                risk_level=health["risk_level"],
            )
        )
        count += 1

        # Seed a demo alert for high-risk RM-002
        if eq.equipment_code == "RM-002" and prediction["failure_probability"] > 0.5:
            existing = await db.scalar(
                select(func.count())
                .select_from(Alert)
                .where(Alert.equipment_id == eq.id, Alert.status == AlertStatus.OPEN)
            )
            if not existing:
                await create_alert(
                    db,
                    equipment_id=eq.id,
                    title="Rolling Mill Motor — elevated failure risk",
                    message=(
                        f"Vibration anomaly detected. Failure probability "
                        f"{prediction['failure_probability']:.0%}. RUL {prediction['remaining_useful_life_hours']:.0f}h. "
                        f"Fault code E-2041 history matches bearing wear pattern."
                    ),
                    level="high" if prediction["failure_probability"] < 0.85 else "critical",
                    source="predictive_maintenance",
                    risk_level=prediction["risk_level"],
                    metadata={"prediction": prediction},
                )

    return count


_LOGBOOK_COLUMNS = [
    ("source_event", "VARCHAR(80)"),
    ("source_id", "INTEGER"),
    ("auto_generated", "BOOLEAN DEFAULT FALSE"),
]


async def _ensure_logbook_columns(conn) -> None:
    """Add auto-logbook columns on existing databases."""
    dialect = conn.dialect.name
    for col_name, col_type in _LOGBOOK_COLUMNS:
        try:
            if dialect == "sqlite":
                await conn.execute(text(f"ALTER TABLE logbook_entries ADD COLUMN {col_name} {col_type}"))
            else:
                await conn.execute(
                    text(f"ALTER TABLE logbook_entries ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
                )
        except Exception:
            pass


async def _backfill_logbook_columns(conn) -> None:
    """Sync legacy rows with new auto-logbook columns."""
    dialect = conn.dialect.name
    try:
        if dialect == "postgres":
            await conn.execute(
                text(
                    "UPDATE logbook_entries SET auto_generated = true "
                    "WHERE auto_generated = false AND metadata_json->>'auto_generated' = 'true'"
                )
            )
            await conn.execute(
                text(
                    "UPDATE logbook_entries SET source_event = metadata_json->>'event_type' "
                    "WHERE source_event IS NULL AND metadata_json->>'event_type' IS NOT NULL"
                )
            )
            await conn.execute(
                text(
                    "UPDATE logbook_entries SET source_event = 'alert.created' "
                    "WHERE source_event IS NULL AND entry_type = 'alert' "
                    "AND title LIKE 'Alert:%'"
                )
            )
            await conn.execute(
                text(
                    "UPDATE logbook_entries SET source_event = 'diagnosis.completed' "
                    "WHERE source_event IS NULL AND entry_type = 'diagnosis'"
                )
            )
    except Exception:
        pass


async def bootstrap_application() -> None:
    from app.core.config import get_settings

    settings = get_settings()
    fresh_seed = False

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_feedback_columns(conn)
        await _ensure_logbook_columns(conn)
        await _backfill_logbook_columns(conn)

    async with AsyncSessionLocal() as db:
        count = await db.scalar(select(func.count()).select_from(Equipment)) or 0
        if count == 0:
            fresh_seed = True
            logger.info("database_empty_running_seed")
            from scripts.seed_data import seed

            await seed()
            async with AsyncSessionLocal() as db:
                n = await run_batch_predictions(db)
                await db.commit()
                logger.info("batch_predictions_after_seed", count=n)
            get_pm_engine()
        else:
            pred_count = await db.scalar(select(func.count()).select_from(Prediction)) or 0
            if pred_count == 0:
                logger.info("running_batch_predictions")
                n = await run_batch_predictions(db)
                await db.commit()
                logger.info("batch_predictions_complete", count=n)
            else:
                await db.commit()

    # Align operational + ML data with problem statement
    try:
        from scripts.seed_operational_data import seed as seed_ops

        await seed_ops()
    except Exception as exc:
        logger.warning("seed_operational_skipped", error=str(exc))

    try:
        engine_ml = get_pm_engine()
        if engine_ml.train_metrics.get("dataset") != "NASA C-MAPSS FD001":
            from scripts.import_cmapss import import_cmapss

            await import_cmapss()
    except Exception as exc:
        logger.warning("import_cmapss_skipped", error=str(exc))

    if fresh_seed or settings.bootstrap_rag_index:
        try:
            from scripts.index_operational_knowledge import index_all

            await index_all()
        except Exception as exc:
            logger.warning("index_operational_skipped", error=str(exc))
    else:
        logger.info("index_operational_skipped", reason="existing_database")

    try:
        from scripts.seed_logbook import seed_logbook as seed_lb

        await seed_lb()
    except Exception as exc:
        logger.warning("seed_logbook_skipped", error=str(exc))

    try:
        from scripts.seed_dependencies import seed_equipment_dependencies

        dep_count = await seed_equipment_dependencies()
        if dep_count:
            logger.info("equipment_dependencies_seeded", count=dep_count)
    except Exception as exc:
        logger.warning("seed_dependencies_skipped", error=str(exc))

    from app.services.live_stream import reset_stream_positions
    from app.services.alerts.alert_engine import prune_alert_backlog

    reset_stream_positions()

    async with AsyncSessionLocal() as db:
        pruned = await prune_alert_backlog(db)
        seeded = await ensure_demo_alerts(db)
        try:
            from app.core.security import get_password_hash
            from app.models import Role, User

            admin_role = await db.scalar(select(Role).where(Role.name == "admin"))
            if admin_role:
                admin_exists = await db.scalar(select(User).where(User.email == "admin@steelplant.com"))
                if not admin_exists:
                    db.add(
                        User(
                            email="admin@steelplant.com",
                            full_name="Demo Administrator",
                            hashed_password=get_password_hash("demo1234"),
                            role_id=admin_role.id,
                        )
                    )
        except Exception as exc:
            logger.warning("ensure_admin_user_skipped", error=str(exc))
        try:
            from app.services.feedback_service import seed_demo_feedback

            fb = await seed_demo_feedback(db)
            if fb:
                logger.info("demo_feedback_seeded", count=fb)
        except Exception as exc:
            logger.warning("seed_feedback_skipped", error=str(exc))
        await db.commit()
        if pruned:
            logger.info("alert_backlog_pruned", count=pruned)
        if seeded:
            logger.info("demo_alerts_seeded", count=seeded)

    metrics = get_pm_engine().train_metrics
    logger.info("ml_ready", metrics=metrics)
