"""Live C-MAPSS sensor stream — plant-calibrated units."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pandas as pd

from app.services.ml.cmapss_loader import cmapss_data_dir, get_unit_trajectory, load_train_fd001, to_plant_features

_trajectories: dict[int, pd.DataFrame] = {}
_positions: dict[int, int] = {}
_loaded = False

# Demo band: stay in mid-degradation (~52–68% health) so the portal looks realistic, not catastrophic
_DEMO_BAND_START = 0.38
_DEMO_BAND_END = 0.52


def _ensure_loaded() -> None:
    global _loaded
    if _loaded:
        return
    path = cmapss_data_dir() / "train_FD001.txt"
    if not path.exists():
        _loaded = True
        return
    df = load_train_fd001(path)
    for unit in range(1, 6):
        traj = get_unit_trajectory(df, unit)
        _trajectories[unit] = traj
        _positions[unit] = int(len(traj) * _DEMO_BAND_START)
    _loaded = True


def reset_stream_positions() -> None:
    """Reset in-memory replay to the demo health band (call on backend startup)."""
    _ensure_loaded()
    for unit, traj in _trajectories.items():
        if traj is not None and not traj.empty:
            _positions[unit] = int(len(traj) * _DEMO_BAND_START)


def map_equipment_to_unit(equipment_id: int) -> int:
    return ((equipment_id - 1) % 5) + 1


def peek_reading(equipment_id: int) -> dict:
    """Current demo-band reading without advancing the replay cursor."""
    _ensure_loaded()
    unit = map_equipment_to_unit(equipment_id)
    traj = _trajectories.get(unit)
    if traj is None or traj.empty:
        return _fallback_reading(equipment_id)

    n = len(traj)
    start_idx = int(n * _DEMO_BAND_START)
    end_idx = max(start_idx + 1, int(n * _DEMO_BAND_END))
    band_len = end_idx - start_idx
    pos = _positions.get(unit, start_idx)
    idx = start_idx + ((pos - start_idx) % band_len)
    row = traj.iloc[idx]
    f = to_plant_features(row)
    return {
        "equipment_id": equipment_id,
        "temperature": f["temperature"],
        "vibration": f["vibration"],
        "pressure": f["pressure"],
        "motor_current": f["motor_current"],
        "health_indicator": f["health_indicator"],
        "cycle": f["cycle"],
        "rul_hours": f["rul_hours"],
        "cmapss_unit": unit,
        "source": "NASA C-MAPSS FD001",
    }


def get_next_reading(equipment_id: int) -> dict:
    _ensure_loaded()
    unit = map_equipment_to_unit(equipment_id)
    traj = _trajectories.get(unit)

    if traj is None or traj.empty:
        return _fallback_reading(equipment_id)

    n = len(traj)
    start_idx = int(n * _DEMO_BAND_START)
    end_idx = max(start_idx + 1, int(n * _DEMO_BAND_END))
    band_len = end_idx - start_idx

    pos = _positions.get(unit, start_idx)
    idx = start_idx + ((pos - start_idx) % band_len)
    row = traj.iloc[idx]
    _positions[unit] = pos + 1

    f = to_plant_features(row)

    return {
        "equipment_id": equipment_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature": f["temperature"],
        "vibration": f["vibration"],
        "pressure": f["pressure"],
        "motor_current": f["motor_current"],
        "health_indicator": f["health_indicator"],
        "cycle": f["cycle"],
        "rul_cycles": f["rul_cycles"],
        "rul_hours": f["rul_hours"],
        "degradation_index": f["degradation_index"],
        "cmapss_unit": unit,
        "cmapss_sensors": f.get("cmapss_sensors", {}),
        "units": {
            "temperature": "°C",
            "vibration": "mm/s",
            "pressure": "bar",
            "motor_current": "A",
        },
        "source": "NASA C-MAPSS FD001",
        "dataset": "FD001",
    }


def _fallback_reading(equipment_id: int) -> dict:
    import math

    t = datetime.now(timezone.utc).timestamp()
    wobble = math.sin(t / 3) * 0.5
    return {
        "equipment_id": equipment_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature": round(78 + wobble * 3, 2),
        "vibration": round(3.2 + wobble, 3),
        "pressure": round(112 + wobble, 2),
        "motor_current": round(58 + wobble, 2),
        "health_indicator": 82.0,
        "source": "simulated plant IoT",
        "units": {"temperature": "°C", "vibration": "mm/s", "pressure": "bar", "motor_current": "A"},
    }


async def stream_readings(equipment_id: int, interval: float = 1.5):
    while True:
        yield get_next_reading(equipment_id)
        await asyncio.sleep(interval)
