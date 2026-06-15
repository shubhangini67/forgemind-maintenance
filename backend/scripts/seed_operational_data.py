"""Seed delay logs + failure incidents for canonical 5-asset fleet (problem statement §4.1)."""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select

from app.core.fleet import CANONICAL_FLEET
from app.db.session import AsyncSessionLocal
from app.models import DelayLog, Equipment, FailureHistory

# Mapped to canonical assets — not friend-project equipment names
DELAY_LOGS = [
    ("BF-001", 0.75, "E003", "High vibration alarm — bearing wear pattern on blower drive", "high"),
    ("BF-001", 3.0, "E003", "Bearing failure shutdown — progressive wear ignored after earlier alarm", "critical"),
    ("RM-002", 12.0, "E-2041", "Rolling mill motor bearing failure — elevated vibration 9.2 mm/s", "critical"),
    ("RM-002", 0.5, "E-2041", "Vibration exceedance during rolling — emergency lubrication applied", "high"),
    ("CP-003", 1.5, "E010", "Discharge pressure anomaly — valve assembly inspection required", "high"),
    ("CW-004", 0.33, "E001", "Cooling pump motor overcurrent trip — phase imbalance corrected", "medium"),
    ("CN-005", 1.0, "E020", "Caster drive encoder feedback fault — coupling replaced", "high"),
    ("CN-005", 0.25, "E003", "Intermittent vibration spike during casting — monitoring increased", "warning"),
]

FAILURES = [
    (
        "RM-002",
        "bearing_failure",
        "E-2041",
        "Elevated vibration leading to bearing overheating during hot rolling",
        "Insufficient lubrication interval — matches SOP alarm thresholds",
        12.0,
    ),
    (
        "BF-001",
        "bearing_failure",
        "E003",
        "Blast furnace blower vibration reached 12.5 mm/s — emergency shutdown",
        "Progressive bearing wear — earlier warning not actioned in time",
        3.0,
    ),
    (
        "CP-003",
        "compressor_fault",
        "E010",
        "Discharge pressure dropped to 185 bar during coke oven push cycle",
        "Internal seal leak in compressor stage",
        1.5,
    ),
    (
        "CW-004",
        "electrical_fault",
        "E001",
        "Pump motor overcurrent trip during peak cooling demand",
        "Loose terminal — single phase fault",
        0.33,
    ),
    (
        "CN-005",
        "drive_fault",
        "E020",
        "Continuous caster drive stopped mid-sequence — encoder signal loss",
        "Encoder coupling wear — intermittent feedback",
        1.0,
    ),
]


async def seed() -> None:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        code_to_id = {
            e.equipment_code: e.id
            for e in (await db.execute(select(Equipment))).scalars().all()
        }

        delay_added = 0
        for code, hours, fault, reason, severity in DELAY_LOGS:
            eq_id = code_to_id.get(code)
            if not eq_id:
                continue
            exists = await db.scalar(
                select(func.count())
                .select_from(DelayLog)
                .where(DelayLog.equipment_id == eq_id, DelayLog.reason == reason)
            )
            if exists:
                continue
            db.add(
                DelayLog(
                    equipment_id=eq_id,
                    delay_hours=hours,
                    fault_code=fault,
                    reason=reason,
                    severity=severity,
                    created_at=now - timedelta(days=delay_added + 1),
                )
            )
            delay_added += 1

        fail_added = 0
        for code, ftype, fault, desc, root, downtime in FAILURES:
            eq_id = code_to_id.get(code)
            if not eq_id:
                continue
            exists = await db.scalar(
                select(func.count())
                .select_from(FailureHistory)
                .where(FailureHistory.equipment_id == eq_id, FailureHistory.fault_code == fault)
            )
            if exists:
                continue
            db.add(
                FailureHistory(
                    equipment_id=eq_id,
                    failure_type=ftype,
                    fault_code=fault,
                    description=desc,
                    root_cause=root,
                    downtime_hours=downtime,
                    occurred_at=now - timedelta(days=30 + fail_added * 15),
                    resolution="Corrective action completed per maintenance SOP",
                )
            )
            fail_added += 1

        await db.commit()
        print(f"Operational seed: {delay_added} delay logs, {fail_added} failure incidents")


if __name__ == "__main__":
    asyncio.run(seed())
