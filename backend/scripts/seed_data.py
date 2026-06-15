"""Seed database with steel plant demo data."""

import asyncio
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.fleet import CANONICAL_FLEET
from app.core.security import get_password_hash
from app.db.session import AsyncSessionLocal, engine
from app.models import (
    Base,
    Document,
    Equipment,
    FailureHistory,
    LogbookEntry,
    MaintenanceRecord,
    ProcurementRequest,
    Role,
    SensorData,
    SparePart,
    User,
)
from app.services.rag.knowledge_engine import get_rag_engine, load_text_file


EQUIPMENT = [
    ("BF-001", "Blast Furnace Blower", "blast_furnace_blower", "Blast Furnace Area", 5),
    ("RM-002", "Rolling Mill Motor", "rolling_mill_motor", "Hot Rolling Mill", 5),
    ("CP-003", "Coke Oven Compressor", "coke_compressor", "Coke Oven Battery", 4),
    ("CW-004", "Cooling Water Pump", "cooling_pump", "Utilities", 3),
    ("CN-005", "Continuous Caster Drive", "caster_drive", "Casting Line", 5),
]

SPARE_PARTS = [
    ("BRG-6205", "Bearing 6205-2RS", "rolling_mill_motor", 8, 5, 450.0, 7),
    ("BLT-A42", "Drive Belt A42", "blast_furnace_blower", 3, 5, 120.0, 10),
    ("Seal-K12", "Mechanical Seal K12", "cooling_pump", 2, 4, 890.0, 21),
    ("VIB-S01", "Vibration Sensor Module", "caster_drive", 6, 3, 1500.0, 14),
    ("MTR-75K", "75kW Motor Winding Kit", "rolling_mill_motor", 1, 2, 12000.0, 30),
]


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        for role_name, desc in [
            ("admin", "System administrator"),
            ("supervisor", "Maintenance supervisor"),
            ("engineer", "Maintenance engineer"),
        ]:
            exists = await db.scalar(select(Role).where(Role.name == role_name))
            if not exists:
                db.add(Role(name=role_name, description=desc))

        await db.flush()

        engineer_role = await db.scalar(select(Role).where(Role.name == "engineer"))
        supervisor_role = await db.scalar(select(Role).where(Role.name == "supervisor"))
        if engineer_role:
            user_exists = await db.scalar(select(User).where(User.email == "engineer@steelplant.com"))
            if not user_exists:
                db.add(
                    User(
                        email="engineer@steelplant.com",
                        full_name="Demo Engineer",
                        hashed_password=get_password_hash("demo1234"),
                        role_id=engineer_role.id,
                    )
                )
        if supervisor_role:
            sup_exists = await db.scalar(select(User).where(User.email == "supervisor@steelplant.com"))
            if not sup_exists:
                db.add(
                    User(
                        email="supervisor@steelplant.com",
                        full_name="Demo Supervisor",
                        hashed_password=get_password_hash("demo1234"),
                        role_id=supervisor_role.id,
                    )
                )
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

        for code, name, etype, location, crit in EQUIPMENT:
            cmapss_unit = next(a["cmapss_unit"] for a in CANONICAL_FLEET if a["code"] == code)
            exists = await db.scalar(select(Equipment).where(Equipment.equipment_code == code))
            if not exists:
                db.add(
                    Equipment(
                        equipment_code=code,
                        name=name,
                        equipment_type=etype,
                        location=location,
                        criticality=crit,
                        manufacturer="Tata Steel OEM",
                        install_date=datetime(2018, 1, 1, tzinfo=timezone.utc),
                        status="operational",
                        metadata_json={
                            "cmapss_unit": cmapss_unit,
                            "cmapss_dataset": "FD001",
                            "data_source": "NASA C-MAPSS",
                            "downtime_cost": crit * 25000,
                        },
                    )
                )

        await db.flush()

        for part_num, name, etype, qty, reorder, cost, lead in SPARE_PARTS:
            exists = await db.scalar(select(SparePart).where(SparePart.part_number == part_num))
            if not exists:
                db.add(
                    SparePart(
                        part_number=part_num,
                        name=name,
                        equipment_type=etype,
                        quantity_available=qty,
                        reorder_level=reorder,
                        unit_cost=cost,
                        supplier="Industrial Spares Ltd",
                        lead_time_days=lead,
                    )
                )

        result = await db.execute(select(Equipment))
        equipment_list = list(result.scalars().all())
        rng = random.Random(42)
        now = datetime.now(timezone.utc)

        for eq in equipment_list:
            for i in range(50):
                degradation = i / 50
                is_anomaly = eq.equipment_code == "RM-002" and i > 40
                db.add(
                    SensorData(
                        equipment_id=eq.id,
                        timestamp=now - timedelta(hours=50 - i),
                        temperature=65 + degradation * 30 + (15 if is_anomaly else 0),
                        vibration=2 + degradation * 5 + (8 if is_anomaly else 0),
                        pressure=100 + degradation * 20,
                        motor_current=50 + degradation * 15,
                        health_indicator=max(30, 100 - degradation * 50 - (20 if is_anomaly else 0)),
                    )
                )

            db.add(
                MaintenanceRecord(
                    equipment_id=eq.id,
                    maintenance_type="preventive",
                    description=f"Quarterly inspection for {eq.name}",
                    performed_by="Maintenance Team A",
                    performed_at=now - timedelta(days=30),
                    duration_hours=4.0,
                    outcome="Completed",
                )
            )

            if eq.equipment_code == "RM-002":
                db.add(
                    FailureHistory(
                        equipment_id=eq.id,
                        failure_type="bearing_failure",
                        fault_code="E-2041",
                        description="Elevated vibration leading to bearing overheating",
                        root_cause="Insufficient lubrication interval",
                        downtime_hours=12.0,
                        occurred_at=now - timedelta(days=90),
                        resolution="Replaced bearing and updated lubrication schedule",
                    )
                )

            lb_exists = await db.scalar(
                select(LogbookEntry).where(LogbookEntry.equipment_id == eq.id).limit(1)
            )
            if not lb_exists:
                db.add(
                    LogbookEntry(
                        equipment_id=eq.id,
                        entry_type="inspection",
                        title=f"Routine inspection — {eq.equipment_code}",
                        description=f"Visual and sensor check completed for {eq.name}. No immediate action required.",
                        observed_by="Demo Engineer",
                    )
                )

        # Sample pending procurement order
        spare = await db.scalar(select(SparePart).where(SparePart.part_number == "BRG-6205"))
        rm = await db.scalar(select(Equipment).where(Equipment.equipment_code == "RM-002"))
        if spare and rm:
            proc_exists = await db.scalar(select(ProcurementRequest).limit(1))
            if not proc_exists:
                db.add(
                    ProcurementRequest(
                        spare_part_id=spare.id,
                        equipment_id=rm.id,
                        quantity=2,
                        urgency="high",
                        status="pending",
                        notes="Low stock bearing for rolling mill motor — C-MAPSS degradation detected",
                    )
                )

        from pathlib import Path

        docs_dir = Path(__file__).resolve().parents[2] / "data" / "documents"
        docs_dir.mkdir(parents=True, exist_ok=True)
        rag = get_rag_engine()

        sample_docs = [
            ("rolling_mill_motor_sop.txt", "Rolling Mill Motor SOP", "sop", "rolling_mill_motor"),
            ("blast_furnace_manual.txt", "Blast Furnace Blower Manual", "manual", "blast_furnace_blower"),
            ("bearing_failure_report.txt", "Bearing Failure Analysis Report", "failure_report", "rolling_mill_motor"),
        ]

        for filename, title, dtype, etype in sample_docs:
            path = docs_dir / filename
            if not path.exists():
                continue
            exists = await db.scalar(select(Document).where(Document.title == title))
            if not exists:
                doc = Document(
                    title=title,
                    document_type=dtype,
                    equipment_type=etype,
                    file_path=str(path),
                    indexed=False,
                )
                db.add(doc)
                await db.flush()
                text = load_text_file(path)
                rag.index_document(doc.id, title, text, dtype, etype)
                doc.indexed = True

        await db.commit()
        print("Seed complete. Login: engineer@steelplant.com / demo1234 (supervisor@steelplant.com / admin@steelplant.com / demo1234)")


if __name__ == "__main__":
    asyncio.run(seed())
