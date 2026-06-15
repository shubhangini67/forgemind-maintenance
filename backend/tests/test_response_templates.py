"""Response template unit tests."""

from app.services.response_templates import build_asset_ranking, build_business_impact


def test_asset_ranking_template():
    state = {
        "query": "Rank all assets by RUL",
        "fleet_snapshot": {
            "assets": [
                {"equipment_code": "BF-001", "name": "Blower", "rul_hours": 100, "failure_probability": 0.5, "risk_level": "high", "health_score": 55},
                {"equipment_code": "RM-002", "name": "Mill", "rul_hours": 500, "failure_probability": 0.2, "risk_level": "medium", "health_score": 72},
            ]
        },
    }
    md, payload = build_asset_ranking(state)
    assert "| Rank | Asset |" in md
    assert len(payload["ranked_assets"]) == 2
    assert payload["ranked_assets"][0]["equipment_code"] == "BF-001"


def test_business_impact_template():
    state = {
        "query": "Production loss if fails now",
        "equipment_context": {"equipment_code": "BF-001"},
        "production_impact": {
            "downtime_estimate_hours": 16,
            "throughput_impact_tons": 280,
            "business_cost_inr": 480000,
            "maintenance_cost_inr": 40000,
            "avoided_loss_inr": 320000,
        },
        "ml_prediction": {"failure_probability": 0.42},
    }
    md, payload = build_business_impact(state)
    assert "Business Impact" in md
    assert payload["production_loss_tons"] == 280
    assert payload["equipment_code"] == "BF-001"
