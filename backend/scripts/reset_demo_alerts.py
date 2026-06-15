"""Resolve spam alerts and seed curated demo alerts for hackathon judges."""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select, update

from app.db.session import AsyncSessionLocal
from app.models import Alert, AlertStatus
from app.services.alerts.alert_engine import ensure_demo_alerts


async def reset() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            update(Alert)
            .where(Alert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]))
            .values(status=AlertStatus.RESOLVED, resolved_at=datetime.now(timezone.utc))
        )
        print(f"Resolved {result.rowcount} alerts")
        seeded = await ensure_demo_alerts(db)
        await db.commit()
        open_count = await db.scalar(
            select(func.count()).select_from(Alert).where(Alert.status == AlertStatus.OPEN)
        )
        print(f"Seeded {seeded} demo alerts — {open_count} open total")


if __name__ == "__main__":
    asyncio.run(reset())
