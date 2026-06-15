"""Business impact analytics — downtime, maintenance cost, savings, ROI."""

from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.fleet import CANONICAL_CODES
from app.models import Equipment, Prediction, SensorData
from app.services.equipment_service import resolve_equipment_health
from app.services.live_stream import peek_reading
from app.services.ml.predictive_engine import pm_engine

# Planned PM cost baseline by asset criticality (INR per intervention window)
PM_BASE_COST: dict[int, int] = {
    1: 75_000,
    2: 100_000,
    3: 150_000,
    4: 200_000,
    5: 250_000,
}

# Predictive maintenance prevention effectiveness baseline
PREVENTION_BASE = 0.68


def compute_asset_business_impact(
    *,
    downtime_cost_per_day: float,
    criticality: int,
    health_score: float,
    rul_hours: float,
    failure_probability: float,
) -> dict:
    """
    Formulas (Tata Steel maintenance economics model):

    expected_downtime_h = 12 + failure_probability × 60  (capped 8–72h)
    downtime_cost       = downtime_cost_per_day × (expected_downtime_h / 24)
    maintenance_cost    = PM_BASE[criticality] × health_multiplier
    prevention_factor   = 68% + (health_score / 100) × 22%  (max 92%)
    avoided_loss        = downtime_cost × failure_probability × prevention_factor × (criticality/5)
    estimated_savings   = avoided_loss − maintenance_cost
    ROI %               = (estimated_savings / maintenance_cost) × 100
    """
    crit = max(1, min(criticality, 5))
    fp = max(0.0, min(float(failure_probability), 1.0))
    health = max(0.0, min(float(health_score), 100.0))
    rul = max(0.0, float(rul_hours))

    expected_downtime_h = min(72.0, max(8.0, 12.0 + fp * 60.0))
    if rul < 48:
        expected_downtime_h = min(72.0, expected_downtime_h + (48 - rul) * 0.15)

    downtime_cost_inr = int(downtime_cost_per_day * expected_downtime_h / 24)

    maintenance_cost_inr = PM_BASE_COST.get(crit, 150_000)
    if health < 45:
        maintenance_cost_inr = int(maintenance_cost_inr * 1.4)
    elif health < 60:
        maintenance_cost_inr = int(maintenance_cost_inr * 1.2)
    elif health < 75:
        maintenance_cost_inr = int(maintenance_cost_inr * 1.08)

    prevention_factor = min(0.92, PREVENTION_BASE + (health / 100) * 0.22)
    avoided_loss_inr = int(downtime_cost_inr * fp * prevention_factor * (crit / 5))
    estimated_savings_inr = max(0, avoided_loss_inr - maintenance_cost_inr)
    roi_pct = round((estimated_savings_inr / max(maintenance_cost_inr, 1)) * 100, 1)

    return {
        "downtime_cost_per_day_inr": int(downtime_cost_per_day),
        "expected_downtime_hours": round(expected_downtime_h, 1),
        "downtime_cost_inr": downtime_cost_inr,
        "maintenance_cost_inr": maintenance_cost_inr,
        "avoided_loss_inr": avoided_loss_inr,
        "estimated_savings_inr": estimated_savings_inr,
        "roi_pct": roi_pct,
        "prevention_factor_pct": round(prevention_factor * 100, 1),
        "is_critical_asset": crit >= 4 or health < 55 or fp >= 0.5,
        "formulas": {
            "expected_downtime_hours": "12 + failure_probability × 60 (cap 72h)",
            "downtime_cost": "downtime_cost_per_day × (expected_downtime_hours / 24)",
            "maintenance_cost": "PM base by criticality × health degradation multiplier",
            "avoided_loss": "downtime_cost × failure_probability × prevention_factor × (criticality/5)",
            "estimated_savings": "avoided_loss − maintenance_cost",
            "roi_pct": "(estimated_savings / maintenance_cost) × 100",
        },
    }


async def compute_plant_business_impact(db: AsyncSession) -> dict:
    eq_result = await db.execute(
        select(Equipment).where(Equipment.equipment_code.in_(CANONICAL_CODES))
    )
    equipment = list(eq_result.scalars().all())
    assets: list[dict] = []

    for eq in equipment:
        meta = eq.metadata_json or {}
        downtime_day = float(meta.get("downtime_cost", eq.criticality * 25_000))

        sensor = (
            await db.execute(
                select(SensorData)
                .where(SensorData.equipment_id == eq.id)
                .order_by(desc(SensorData.timestamp))
                .limit(1)
            )
        ).scalar_one_or_none()
        health = await resolve_equipment_health(db, eq.id, sensor)

        live = peek_reading(eq.id)
        live_pred = pm_engine.predict_rul({
            "temperature": live["temperature"],
            "vibration": live["vibration"],
            "pressure": live["pressure"],
            "motor_current": live["motor_current"],
            "health_indicator": live["health_indicator"],
        })
        fp = float(live_pred.get("failure_probability") or 0.4)
        rul = float(live_pred.get("remaining_useful_life_hours") or live.get("rul_hours") or 0)

        pred_row = await db.scalar(
            select(Prediction)
            .where(Prediction.equipment_id == eq.id)
            .order_by(desc(Prediction.created_at))
            .limit(1)
        )
        if pred_row:
            fp = float(pred_row.failure_probability or fp)
            rul = float(pred_row.remaining_useful_life_hours or rul)

        impact = compute_asset_business_impact(
            downtime_cost_per_day=downtime_day,
            criticality=eq.criticality,
            health_score=health,
            rul_hours=rul,
            failure_probability=fp,
        )
        assets.append({
            "equipment_id": eq.id,
            "equipment_code": eq.equipment_code,
            "name": eq.name,
            "location": eq.location,
            "criticality": eq.criticality,
            "health_score": round(health, 1),
            "rul_hours": round(rul, 1),
            "failure_probability": round(fp, 3),
            **impact,
        })

    critical_assets = [a for a in assets if a["is_critical_asset"]]
    fleet = {
        "total_downtime_cost_inr": sum(a["downtime_cost_inr"] for a in assets),
        "total_maintenance_cost_inr": sum(a["maintenance_cost_inr"] for a in assets),
        "total_avoided_loss_inr": sum(a["avoided_loss_inr"] for a in assets),
        "total_estimated_savings_inr": sum(a["estimated_savings_inr"] for a in assets),
        "fleet_roi_pct": round(
            (sum(a["estimated_savings_inr"] for a in assets) / max(sum(a["maintenance_cost_inr"] for a in assets), 1))
            * 100,
            1,
        ),
        "critical_asset_count": len(critical_assets),
        "assets_analysed": len(assets),
    }

    return {
        "assets": sorted(assets, key=lambda a: a["estimated_savings_inr"], reverse=True),
        "critical_assets": sorted(critical_assets, key=lambda a: a["roi_pct"], reverse=True),
        "fleet_summary": fleet,
        "methodology": {
            "description": "Predictive maintenance ROI model for Tata Steel Jamshedpur — C-MAPSS-mapped critical assets",
            "currency": "INR",
            "period": "Per intervention window (typically 90 days)",
        },
    }


def build_executive_summary_narrative(data: dict) -> str:
    fleet = data["fleet_summary"]
    top = data["critical_assets"][:3] if data["critical_assets"] else data["assets"][:3]
    lines = [
        "## Executive Summary — Business Impact",
        "",
        f"**Fleet ROI:** {fleet['fleet_roi_pct']}% across {fleet['assets_analysed']} C-MAPSS-mapped assets.",
        f"**Estimated savings:** ₹{fleet['total_estimated_savings_inr']:,} by avoiding unplanned downtime through predictive maintenance.",
        f"**Avoided loss:** ₹{fleet['total_avoided_loss_inr']:,} | **Planned maintenance investment:** ₹{fleet['total_maintenance_cost_inr']:,}",
        "",
        "### Top critical assets by business value",
    ]
    for a in top:
        lines.append(
            f"- **{a['equipment_code']}** ({a['name']}): ROI {a['roi_pct']}%, "
            f"savings ₹{a['estimated_savings_inr']:,}, downtime exposure ₹{a['downtime_cost_inr']:,}"
        )
    lines.extend([
        "",
        "### Recommendation",
        "Prioritize PM on assets where RUL < spare lead time and ROI exceeds 100%. "
        "Maintenance Wizard AI reduces failure probability through early RUL detection and spare-aware scheduling.",
    ])
    return "\n".join(lines)
