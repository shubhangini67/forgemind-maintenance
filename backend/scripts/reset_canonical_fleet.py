"""Reset database to canonical 5-asset C-MAPSS fleet — removes expand_fleet junk."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select, update

from app.core.fleet import CANONICAL_CODES, CANONICAL_FLEET
from app.db.session import AsyncSessionLocal
from app.models import (
    Alert,
    Conversation,
    DelayLog,
    Equipment,
    EquipmentHealthScore,
    FailureHistory,
    Feedback,
    LogbookEntry,
    MaintenanceRecord,
    Prediction,
    ProcurementRequest,
    SensorData,
)


async def reset() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Equipment))
        all_eq = list(result.scalars().all())
        junk = [e for e in all_eq if e.equipment_code not in CANONICAL_CODES]
        junk_ids = [e.id for e in junk]

        if junk_ids:
            for model, col in [
                (SensorData, SensorData.equipment_id),
                (Prediction, Prediction.equipment_id),
                (EquipmentHealthScore, EquipmentHealthScore.equipment_id),
                (Alert, Alert.equipment_id),
                (MaintenanceRecord, MaintenanceRecord.equipment_id),
                (FailureHistory, FailureHistory.equipment_id),
                (DelayLog, DelayLog.equipment_id),
                (LogbookEntry, LogbookEntry.equipment_id),
                (Feedback, Feedback.equipment_id),
            ]:
                await db.execute(delete(model).where(col.in_(junk_ids)))
            await db.execute(
                update(Conversation)
                .where(Conversation.equipment_id.in_(junk_ids))
                .values(equipment_id=None)
            )
            await db.execute(delete(Equipment).where(Equipment.id.in_(junk_ids)))
            print(f"Removed {len(junk_ids)} non-canonical assets (sinter fan, expanded fleet, etc.)")

        for spec in CANONICAL_FLEET:
            eq = await db.scalar(select(Equipment).where(Equipment.equipment_code == spec["code"]))
            if eq:
                eq.name = spec["name"]
                eq.equipment_type = spec["equipment_type"]
                eq.location = spec["location"]
                eq.criticality = spec["criticality"]
                eq.metadata_json = {
                    "cmapss_unit": spec["cmapss_unit"],
                    "cmapss_dataset": "FD001",
                    "data_source": "NASA C-MAPSS",
                    "downtime_cost": spec["criticality"] * 25000,
                }
            else:
                print(f"  Missing {spec['code']} — run seed_data.py first")

        await db.commit()
        remaining = list((await db.execute(select(Equipment))).scalars().all())
        print(f"Canonical fleet: {len(remaining)} assets — {[e.equipment_code for e in remaining]}")


if __name__ == "__main__":
    asyncio.run(reset())
