"""Seed logbook entries for canonical 5-asset fleet."""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.fleet import CANONICAL_FLEET
from app.db.session import AsyncSessionLocal
from app.models import Equipment, LogbookEntry

SAMPLE_ENTRIES = [
    ("inspection", "Routine vibration check", "Vibration within limits. C-MAPSS cycle logged."),
    ("observation", "Temperature drift noted", "Slight upward trend on s_4 sensor — monitoring every 2h."),
    ("repair", "Bearing lubrication service", "Completed scheduled lube per SOP. Health improved 3%."),
]


async def seed_logbook() -> None:
    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)
        created = 0
        for spec in CANONICAL_FLEET:
            eq = await db.scalar(select(Equipment).where(Equipment.equipment_code == spec["code"]))
            if not eq:
                print(f"  Skip {spec['code']} — not in DB")
                continue
            existing = await db.scalar(
                select(LogbookEntry).where(LogbookEntry.equipment_id == eq.id).limit(1)
            )
            if existing:
                continue
            for i, (etype, title, desc) in enumerate(SAMPLE_ENTRIES):
                db.add(
                    LogbookEntry(
                        equipment_id=eq.id,
                        entry_type=etype,
                        title=f"{title} — {spec['code']}",
                        description=f"{desc} Asset: {spec['name']}.",
                        observed_by="Demo Engineer",
                        created_at=now - timedelta(days=10 - i * 2),
                    )
                )
                created += 1
        await db.commit()
        total = await db.scalar(select(LogbookEntry))
        count = len(list((await db.execute(select(LogbookEntry))).scalars().all()))
        print(f"Added {created} logbook entries. Total in DB: {count}")


if __name__ == "__main__":
    asyncio.run(seed_logbook())
