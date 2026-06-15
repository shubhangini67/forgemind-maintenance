from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Alert, EquipmentHealthScore, Prediction, SensorData, User
from app.schemas import (
    AlertResponse,
    DashboardSummary,
    EquipmentResponse,
    HealthScoreResponse,
    MaintenanceRecordResponse,
    PredictionResponse,
    SensorDataCreate,
    SensorDataResponse,
    SparePartResponse,
)
from app.services.alerts.alert_engine import process_sensor_and_alert
from app.services.equipment_service import (
    get_dashboard_summary,
    get_equipment,
    get_failure_history,
    get_maintenance_history,
    get_plant_priority,
    get_plant_twin,
    ingest_sensor_reading,
    list_equipment,
    list_spare_parts,
)
from app.services.ml.predictive_engine import pm_engine

router = APIRouter(prefix="/equipment", tags=["equipment"])


@router.get("/dashboard", response_model=DashboardSummary)
async def dashboard(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    return await get_dashboard_summary(db)


@router.get("", response_model=list[EquipmentResponse])
async def equipment_list(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    items = await list_equipment(db)
    return [EquipmentResponse.model_validate(e) for e in items]


@router.get("/plant-twin")
async def plant_twin(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    return await get_plant_twin(db)


@router.get("/priority")
async def plant_priority(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    return await get_plant_priority(db)


@router.get("/spares/all", response_model=list[SparePartResponse])
async def spares(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    parts = await list_spare_parts(db)
    return [SparePartResponse.model_validate(p) for p in parts]


@router.get("/{equipment_id}", response_model=EquipmentResponse)
async def equipment_detail(
    equipment_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)
):
    item = await get_equipment(db, equipment_id)
    if not item:
        raise HTTPException(status_code=404, detail="Equipment not found")
    return EquipmentResponse.model_validate(item)


@router.get("/{equipment_id}/sensors", response_model=list[SensorDataResponse])
async def sensor_history(
    equipment_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)
):
    result = await db.execute(
        select(SensorData)
        .where(SensorData.equipment_id == equipment_id)
        .order_by(desc(SensorData.timestamp))
        .limit(100)
    )
    return [SensorDataResponse.model_validate(s) for s in result.scalars().all()]


@router.post("/{equipment_id}/sensors", response_model=SensorDataResponse)
async def add_sensor_reading(
    equipment_id: int,
    data: SensorDataCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    reading = await ingest_sensor_reading(
        db,
        equipment_id,
        {
            "temperature": data.temperature,
            "vibration": data.vibration,
            "pressure": data.pressure,
            "motor_current": data.motor_current,
            "health_indicator": data.health_indicator,
        },
    )
    sensor_dict = {
        "temperature": data.temperature,
        "vibration": data.vibration,
        "pressure": data.pressure,
        "motor_current": data.motor_current,
        "health_indicator": data.health_indicator,
    }
    await process_sensor_and_alert(db, equipment_id, sensor_dict)

    prediction = pm_engine.predict_rul(sensor_dict)
    health = pm_engine.compute_health_score(sensor_dict, prediction)
    db.add(
        Prediction(
            equipment_id=equipment_id,
            failure_probability=prediction["failure_probability"],
            degradation_score=prediction["degradation_score"],
            remaining_useful_life_hours=prediction["remaining_useful_life_hours"],
            risk_level=prediction["risk_level"],
            model_version=prediction["model_version"],
            features_used=prediction["features_used"],
            explanation=prediction["explanation"],
        )
    )
    db.add(
        EquipmentHealthScore(
            equipment_id=equipment_id,
            health_score=health["health_score"],
            degradation_trend=health["degradation_trend"],
            risk_level=health["risk_level"],
        )
    )
    await db.flush()
    return SensorDataResponse.model_validate(reading)


@router.get("/{equipment_id}/predictions", response_model=PredictionResponse | None)
async def latest_prediction(
    equipment_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Prediction)
        .where(Prediction.equipment_id == equipment_id)
        .order_by(desc(Prediction.created_at))
        .limit(1)
    )
    pred = result.scalar_one_or_none()
    return PredictionResponse.model_validate(pred) if pred else None


@router.get("/{equipment_id}/health", response_model=HealthScoreResponse | None)
async def latest_health(
    equipment_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)
):
    result = await db.execute(
        select(EquipmentHealthScore)
        .where(EquipmentHealthScore.equipment_id == equipment_id)
        .order_by(desc(EquipmentHealthScore.computed_at))
        .limit(1)
    )
    score = result.scalar_one_or_none()
    return HealthScoreResponse.model_validate(score) if score else None


@router.get("/{equipment_id}/maintenance", response_model=list[MaintenanceRecordResponse])
async def maintenance_history(
    equipment_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)
):
    records = await get_maintenance_history(db, equipment_id)
    return [MaintenanceRecordResponse.model_validate(r) for r in records]
