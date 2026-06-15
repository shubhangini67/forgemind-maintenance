import pytest
from app.services.ml.predictive_engine import PredictiveMaintenanceEngine, RiskScoringEngine


def test_anomaly_detection():
    engine = PredictiveMaintenanceEngine()
    normal = {
        "temperature": 70,
        "vibration": 3,
        "pressure": 110,
        "motor_current": 55,
        "health_indicator": 85,
    }
    result = engine.detect_anomaly(normal)
    assert "is_anomaly" in result
    assert "anomaly_score" in result


def test_rul_prediction():
    engine = PredictiveMaintenanceEngine()
    reading = {
        "temperature": 90,
        "vibration": 7,
        "pressure": 130,
        "motor_current": 65,
        "health_indicator": 55,
    }
    result = engine.predict_rul(reading)
    assert result["remaining_useful_life_hours"] >= 0
    assert 0 <= result["failure_probability"] <= 1
    assert result["risk_level"] is not None


def test_risk_scoring_rul_lead_escalation():
    engine = RiskScoringEngine()
    # Bearing stock=0, lead=12d, RUL=5d (120h) → should escalate to CRITICAL
    result = engine.compute(
        criticality=5,
        failure_probability=0.75,
        downtime_cost=100000,
        spare_availability=0,
        lead_time_days=12,
        rul_hours=120,
        reorder_level=5,
    )
    assert result["risk_level"].value == "critical"
    assert result["procurement_risk"] == "critical"
    assert result["escalated"] is True
    assert result["escalation_reason"] is not None


def test_risk_scoring():
    engine = RiskScoringEngine()
    result = engine.compute(
        criticality=5,
        failure_probability=0.8,
        downtime_cost=100000,
        spare_availability=1,
        lead_time_days=30,
    )
    assert result["overall_risk_score"] > 0
    assert result["risk_level"] is not None
