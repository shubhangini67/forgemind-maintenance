"""Import NASA C-MAPSS FD001 — train models and seed PostgreSQL."""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from sqlalchemy import delete, select

from app.db.session import AsyncSessionLocal, engine
from app.models import (
    Base,
    Equipment,
    EquipmentHealthScore,
    Prediction,
    RiskLevel,
    SensorData,
)
from app.services.ml.cmapss_loader import (
    build_training_frame,
    get_degrading_units,
    get_unit_trajectory,
    load_train_fd001,
    to_plant_features,
)
from app.services.ml.predictive_engine import get_pm_engine


async def import_cmapss() -> None:
    print("Loading NASA C-MAPSS FD001...")
    df = load_train_fd001()
    print(f"  {len(df)} rows, {df['unit'].nunique()} engines")

    print("Training ML on real C-MAPSS data...")
    train_df = build_training_frame(df)
    engine_ml = get_pm_engine()
    features = ["temperature", "vibration", "pressure", "motor_current", "health_indicator"]
    from sklearn.preprocessing import StandardScaler
    from sklearn.ensemble import IsolationForest
    from xgboost import XGBRegressor
    import joblib
    import numpy as np

    scaler = StandardScaler()
    X = scaler.fit_transform(train_df[features])
    iso = IsolationForest(contamination=0.05, random_state=42)
    iso.fit(X)
    rul_model = XGBRegressor(n_estimators=150, max_depth=6, learning_rate=0.08, random_state=42)
    rul_model.fit(X, train_df["rul_hours"])

    mae = float(np.mean(np.abs(rul_model.predict(X) - train_df["rul_hours"])))
    engine_ml.scaler = scaler
    engine_ml.iso_forest = iso
    engine_ml.rul_model = rul_model
    engine_ml.train_metrics = {
        "dataset": "NASA C-MAPSS FD001",
        "samples": len(train_df),
        "rul_mae_hours": round(mae, 2),
        "engines": int(df["unit"].nunique()),
        "model_version": "xgb-cmapss-v1",
    }
    joblib.dump(scaler, engine_ml.scaler_path)
    joblib.dump(iso, engine_ml.iso_path)
    joblib.dump(rul_model, engine_ml.rul_path)
    engine_ml.metrics_path.write_text(__import__("json").dumps(engine_ml.train_metrics, indent=2))
    print(f"  Trained — RUL MAE: {mae:.1f} hours")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    units = get_degrading_units(df, n=5)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Equipment).order_by(Equipment.id))
        equipment_list = list(result.scalars().all())
        if not equipment_list:
            print("No equipment found — run seed_data.py first")
            return

        # Clear old synthetic sensor data
        for eq in equipment_list:
            await db.execute(delete(SensorData).where(SensorData.equipment_id == eq.id))
            await db.execute(delete(Prediction).where(Prediction.equipment_id == eq.id))
            await db.execute(delete(EquipmentHealthScore).where(EquipmentHealthScore.equipment_id == eq.id))

        now = datetime.now(timezone.utc)
        for i, eq in enumerate(equipment_list[:5]):
            unit = units[i % len(units)]
            traj = get_unit_trajectory(df, unit)
            # Last 80 cycles for history + use final cycles for degradation demo
            sample = traj.tail(80)
            eq.metadata_json = {
                **(eq.metadata_json or {}),
                "cmapss_unit": int(unit),
                "cmapss_dataset": "FD001",
                "data_source": "NASA C-MAPSS",
            }
            for j, (_, row) in enumerate(sample.iterrows()):
                f = to_plant_features(row)
                db.add(
                    SensorData(
                        equipment_id=eq.id,
                        timestamp=now - timedelta(hours=80 - j),
                        temperature=f["temperature"],
                        vibration=f["vibration"],
                        pressure=f["pressure"],
                        motor_current=f["motor_current"],
                        health_indicator=f["health_indicator"],
                        raw_data={"cmapss_unit": unit, "cycle": f["cycle"], "rul_cycles": f["rul_cycles"]},
                    )
                )

            latest = to_plant_features(traj.iloc[-1])
            pred = engine_ml.predict_rul(latest)
            health = engine_ml.compute_health_score(latest, pred)
            db.add(
                Prediction(
                    equipment_id=eq.id,
                    failure_probability=pred["failure_probability"],
                    degradation_score=pred["degradation_score"],
                    remaining_useful_life_hours=pred["remaining_useful_life_hours"],
                    risk_level=pred["risk_level"],
                    model_version="xgb-cmapss-v1",
                    features_used=pred["features_used"],
                    explanation=f"[C-MAPSS Unit {unit}] {pred['explanation']}",
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
            print(f"  {eq.equipment_code} ← C-MAPSS unit {unit}, RUL {pred['remaining_useful_life_hours']:.0f}h")

        await db.commit()
    print("C-MAPSS import complete.")


if __name__ == "__main__":
    asyncio.run(import_cmapss())
