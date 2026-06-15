"""DEPRECATED — do not run. This script added fake assets (Sinter Fan, etc.) not in the canonical 5-asset C-MAPSS fleet.

Use scripts/reset_canonical_fleet.py instead to restore BF-001, RM-002, CP-003, CW-004, CN-005 only.
"""

raise SystemExit(
    "expand_fleet.py is disabled. Your project uses 5 C-MAPSS-mapped assets only. "
    "Run: python scripts/reset_canonical_fleet.py"
)

import asyncio
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db.session import AsyncSessionLocal, engine
from app.models import Base, Equipment, EquipmentHealthScore, RiskLevel, SensorData

# (code, name, type, location, sector, criticality)
FLEET = [
    ("BF-001", "Blast Furnace Blower", "blast_furnace_blower", "Blast Furnace Area", "Blast Furnace", 5),
    ("BF-CP-001", "Blast Furnace Cooling Pump #1", "cooling_pump", "Blast Furnace Area", "Blast Furnace", 5),
    ("BF-HB-001", "Hot Blast Blower", "blast_furnace_blower", "Blast Furnace Area", "Blast Furnace", 5),
    ("BF-ST-001", "BF Stack Thermocouple Array", "sensor_array", "Blast Furnace Area", "Blast Furnace", 4),
    ("BF-DM-001", "Dust Collector Motor", "motor_drive", "Blast Furnace Area", "Blast Furnace", 3),
    ("RM-002", "Rolling Mill Motor", "rolling_mill_motor", "Hot Rolling Mill", "Rolling Mill", 5),
    ("RM-GB-001", "Mill Gearbox #1", "gearbox", "Hot Rolling Mill", "Rolling Mill", 5),
    ("RM-WR-001", "Wire Rod Mill Drive", "rolling_mill_motor", "Hot Rolling Mill", "Rolling Mill", 4),
    ("RM-CO-001", "Coiler Drive Motor", "motor_drive", "Hot Rolling Mill", "Rolling Mill", 4),
    ("RM-FN-001", "Finishing Mill Fan", "blast_furnace_blower", "Hot Rolling Mill", "Rolling Mill", 3),
    ("CP-003", "Coke Oven Compressor", "coke_compressor", "Coke Oven Battery", "Coke Oven", 4),
    ("CO-FN-001", "Coke Oven Exhaust Fan", "blast_furnace_blower", "Coke Oven Battery", "Coke Oven", 4),
    ("CO-PY-001", "Pusher Machine Hydraulic Pump", "cooling_pump", "Coke Oven Battery", "Coke Oven", 3),
    ("PP-TG-001", "Steam Turbine Generator", "turbine_generator", "Power Plant", "Power Plant", 5),
    ("PP-BF-001", "Boiler Feed Pump", "cooling_pump", "Power Plant", "Power Plant", 4),
    ("PP-CW-001", "Condenser Water Pump", "cooling_pump", "Power Plant", "Power Plant", 4),
    ("PP-TR-001", "Transformer Cooling Fan", "motor_drive", "Power Plant", "Power Plant", 3),
    ("SMS-EAF-001", "EAF Electrode Drive", "caster_drive", "Steel Melting Shop", "Steel Melting Shop", 5),
    ("SMS-LF-001", "Ladle Furnace Blower", "blast_furnace_blower", "Steel Melting Shop", "Steel Melting Shop", 4),
    ("SMS-CR-001", "Continuous Caster #1", "caster_drive", "Steel Melting Shop", "Steel Melting Shop", 5),
    ("SMS-OV-001", "Overhead Crane Motor", "motor_drive", "Steel Melting Shop", "Steel Melting Shop", 4),
    ("SMS-AG-001", "Argon Stirring Unit", "coke_compressor", "Steel Melting Shop", "Steel Melting Shop", 3),
    ("SP-FN-001", "Sinter Fan Main Blower", "blast_furnace_blower", "Sinter Plant", "Sinter Plant", 5),
    ("SP-DR-001", "Sinter Machine Drive", "rolling_mill_motor", "Sinter Plant", "Sinter Plant", 4),
    ("SP-DC-001", "Dedusting Cyclone Motor", "motor_drive", "Sinter Plant", "Sinter Plant", 3),
]


async def expand() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        rng = random.Random(42)
        now = datetime.now(timezone.utc)
        added = 0

        for code, name, etype, location, sector, crit in FLEET:
            exists = await db.scalar(select(Equipment).where(Equipment.equipment_code == code))
            if exists:
                meta = exists.metadata_json or {}
                meta["plant_sector"] = sector
                exists.metadata_json = meta
                continue

            eq = Equipment(
                equipment_code=code,
                name=name,
                equipment_type=etype,
                location=location,
                criticality=crit,
                manufacturer="Tata Steel OEM",
                install_date=datetime(2017 + rng.randint(0, 4), 1, 1, tzinfo=timezone.utc),
                status="operational",
                metadata_json={
                    "plant_sector": sector,
                    "downtime_cost": crit * 25000,
                    "data_source": "NASA C-MAPSS",
                },
            )
            db.add(eq)
            await db.flush()

            degradation = rng.uniform(0.2, 0.85)
            health = max(35, min(95, 100 - degradation * 55))
            for i in range(30):
                d = degradation + i * 0.005
                db.add(
                    SensorData(
                        equipment_id=eq.id,
                        timestamp=now - timedelta(hours=30 - i),
                        temperature=round(68 + d * 45, 2),
                        vibration=round(2 + d * 8, 3),
                        pressure=round(105 + d * 25, 2),
                        motor_current=round(48 + d * 28, 2),
                        health_indicator=round(max(0, health - i * 0.3), 2),
                    )
                )
            db.add(
                EquipmentHealthScore(
                    equipment_id=eq.id,
                    health_score=round(health, 1),
                    degradation_trend="degrading" if health < 60 else "stable",
                    risk_level=RiskLevel.HIGH if health < 50 else RiskLevel.MEDIUM if health < 70 else RiskLevel.LOW,
                )
            )
            added += 1
            print(f"  + {code} ({sector}) health={health:.0f}%")

        await db.commit()
        total = await db.scalar(select(Equipment).where(True).limit(1))
        count = len(list((await db.execute(select(Equipment))).scalars().all()))
        print(f"Fleet expanded: {added} new assets, {count} total")


if __name__ == "__main__":
    asyncio.run(expand())
