"""Index maintenance history, failures, and logbook into RAG (problem statement §4.3)."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models import Equipment, FailureHistory, LogbookEntry, MaintenanceRecord
from app.services.rag.knowledge_engine import get_rag_engine

BASE_ID = 9000


async def index_all() -> None:
    rag = get_rag_engine()
    indexed = 0
    async with AsyncSessionLocal() as db:
        equipment = {e.id: e for e in (await db.execute(select(Equipment))).scalars().all()}

        for rec in (await db.execute(select(MaintenanceRecord))).scalars().all():
            eq = equipment.get(rec.equipment_id)
            text = (
                f"Maintenance Record — {eq.equipment_code if eq else rec.equipment_id}\n"
                f"Type: {rec.maintenance_type}\n"
                f"Description: {rec.description}\n"
                f"Performed by: {rec.performed_by}\n"
                f"Outcome: {rec.outcome}\n"
            )
            rag.index_document(
                BASE_ID + rec.id,
                f"Maintenance — {eq.name if eq else rec.equipment_id}",
                text,
                "maintenance_record",
                eq.equipment_type if eq else None,
            )
            indexed += 1

        for fail in (await db.execute(select(FailureHistory))).scalars().all():
            eq = equipment.get(fail.equipment_id)
            text = (
                f"Failure Incident — {eq.equipment_code if eq else fail.equipment_id}\n"
                f"Fault code: {fail.fault_code}\n"
                f"Type: {fail.failure_type}\n"
                f"Description: {fail.description}\n"
                f"Root cause: {fail.root_cause}\n"
                f"Downtime: {fail.downtime_hours}h\n"
                f"Resolution: {fail.resolution}\n"
            )
            rag.index_document(
                BASE_ID + 500 + fail.id,
                f"Failure Report — {fail.fault_code}",
                text,
                "failure_report",
                eq.equipment_type if eq else None,
            )
            indexed += 1

        for entry in (await db.execute(select(LogbookEntry))).scalars().all():
            eq = equipment.get(entry.equipment_id)
            text = f"Logbook {entry.entry_type}: {entry.title}\n{entry.description}\nObserved by: {entry.observed_by}"
            rag.index_document(
                BASE_ID + 1000 + entry.id,
                f"Logbook — {entry.title}",
                text,
                "logbook",
                eq.equipment_type if eq else None,
            )
            indexed += 1

    print(f"Indexed {indexed} operational records into RAG")


if __name__ == "__main__":
    asyncio.run(index_all())
