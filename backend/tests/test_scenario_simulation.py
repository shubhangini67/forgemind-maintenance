"""Scenario simulation engine tests."""

from app.services.scenario_simulation_engine import (
    build_simulation_markdown,
    run_scenario_simulation,
)


def test_standard_horizons_and_markdown_table():
    sim = run_scenario_simulation(
        query="What happens if maintenance is delayed by 7 days?",
        equipment_context={"equipment_code": "BF-001", "criticality": 5, "downtime_cost": 120000},
        sensor_reading={"temperature": 85, "vibration": 5.2, "health_indicator": 58},
        spare_context=[{"quantity_available": 2, "lead_time_days": 14, "reorder_level": 3}],
        operational_context={"delay_logs": [1, 2, 3]},
        force_standard_horizons=True,
    )
    assert len(sim["projections"]) == 4
    labels = [p["label"] for p in sim["projections"]]
    assert labels == ["+1 Day", "+3 Days", "+7 Days", "+14 Days"]

    md = build_simulation_markdown(sim, equipment_code="BF-001", query="delay 7 days")
    assert "| Scenario | RUL | Failure Probability | Risk | Downtime Cost |" in md
    assert "| Current |" in md
    assert "+7 Days" in md
    assert "### Business Impact Summary" in md
    assert "### Recommended Action" in md
