"""Seed equipment dependency graph for failure cascade modelling."""

from sqlalchemy import func, select

from app.core.fleet import DEFAULT_DEPENDENCIES
from app.db.session import AsyncSessionLocal
from app.models import Equipment, EquipmentDependency


async def seed_equipment_dependencies() -> int:
    async with AsyncSessionLocal() as db:
        existing = await db.scalar(select(func.count()).select_from(EquipmentDependency)) or 0
        if existing > 0:
            return 0

        eq_result = await db.execute(select(Equipment))
        by_code = {eq.equipment_code: eq for eq in eq_result.scalars().all()}
        count = 0
        for dep in DEFAULT_DEPENDENCIES:
            up = by_code.get(dep["upstream"])
            down = by_code.get(dep["downstream"])
            if not up or not down:
                continue
            db.add(
                EquipmentDependency(
                    upstream_equipment_id=up.id,
                    downstream_equipment_id=down.id,
                    dependency_type=dep["type"],
                    impact_weight=dep["weight"],
                    production_share_pct=dep["share_pct"],
                    description=dep["desc"],
                )
            )
            count += 1
        await db.commit()
        return count
