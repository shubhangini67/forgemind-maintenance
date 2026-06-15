"""NASA C-MAPSS FD001 loader — raw sensors mapped to steel-plant units."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from app.core.config import get_settings

CMAPSS_COLUMNS = (
    ["unit", "cycle"]
    + [f"op_{i}" for i in range(1, 4)]
    + [f"s_{i}" for i in range(1, 22)]
)

# FD001 sensors mapped to plant channels (NASA turbofan degradation signatures)
SENSOR_MAP = {
    "temperature": "s_4",
    "vibration": "s_8",
    "pressure": "s_11",
    "motor_current": "s_15",
}

PLANT_RANGES = {
    "temperature": (65.0, 125.0),
    "vibration": (1.5, 12.0),
    "pressure": (95.0, 145.0),
    "motor_current": (40.0, 90.0),
}

_sensor_stats: dict[str, tuple[float, float]] | None = None


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def cmapss_data_dir() -> Path:
    root = get_settings().resolved_data_dir / "cmapss"
    root.mkdir(parents=True, exist_ok=True)
    return root


def load_train_fd001(path: Path | None = None) -> pd.DataFrame:
    path = path or cmapss_data_dir() / "train_FD001.txt"
    if not path.exists():
        raise FileNotFoundError(f"C-MAPSS train file not found: {path}")
    return pd.read_csv(path, sep=r"\s+", header=None, names=CMAPSS_COLUMNS)


def get_sensor_stats(df: pd.DataFrame | None = None) -> dict[str, tuple[float, float]]:
    """Min/max per mapped C-MAPSS sensor column from FD001 training data."""
    global _sensor_stats
    if _sensor_stats is not None:
        return _sensor_stats
    if df is None:
        path = cmapss_data_dir() / "train_FD001.txt"
        if not path.exists():
            _sensor_stats = {col: (0.0, 1.0) for col in SENSOR_MAP.values()}
            return _sensor_stats
        df = load_train_fd001(path)
    _sensor_stats = {}
    for col in SENSOR_MAP.values():
        _sensor_stats[col] = (float(df[col].min()), float(df[col].max()))
    return _sensor_stats


def _map_raw_to_plant(raw: float, col: str, plant_key: str) -> float:
    stats = get_sensor_stats()
    lo_raw, hi_raw = stats.get(col, (0.0, 1.0))
    span = max(hi_raw - lo_raw, 1e-6)
    normalized = _clamp((raw - lo_raw) / span, 0.0, 1.0)
    p_lo, p_hi = PLANT_RANGES[plant_key]
    return _clamp(p_lo + normalized * (p_hi - p_lo), p_lo, p_hi)


def compute_rul_labels(df: pd.DataFrame) -> pd.DataFrame:
    max_cycles = df.groupby("unit")["cycle"].max()
    out = df.copy()
    out["rul_cycles"] = out.apply(lambda r: max_cycles[r["unit"]] - r["cycle"], axis=1)
    out["rul_hours"] = out["rul_cycles"] * 10.0
    return out


def to_plant_features(row: pd.Series) -> dict[str, float | int]:
    """Map C-MAPSS engine cycle → steel plant channels using raw NASA sensor columns."""
    max_cycle = float(row.get("max_cycle", row["cycle"] + row.get("rul_cycles", 1)))
    rul_cycles = float(row.get("rul_cycles", 0))
    health_pct = _clamp(100.0 * rul_cycles / max(max_cycle, 1.0), 0.0, 100.0)
    degradation = 1.0 - health_pct / 100.0
    cycle = int(row["cycle"])

    # Raw C-MAPSS sensor → plant unit conversion
    temperature = _map_raw_to_plant(float(row[SENSOR_MAP["temperature"]]), SENSOR_MAP["temperature"], "temperature")
    vibration = _map_raw_to_plant(float(row[SENSOR_MAP["vibration"]]), SENSOR_MAP["vibration"], "vibration")
    pressure = _map_raw_to_plant(float(row[SENSOR_MAP["pressure"]]), SENSOR_MAP["pressure"], "pressure")
    motor_current = _map_raw_to_plant(float(row[SENSOR_MAP["motor_current"]]), SENSOR_MAP["motor_current"], "motor_current")

    # Blend RUL degradation curve (10%) so health index aligns with ML training
    for key, val in [
        ("temperature", temperature),
        ("vibration", vibration),
        ("pressure", pressure),
        ("motor_current", motor_current),
    ]:
        p_lo, p_hi = PLANT_RANGES[key]
        degraded = p_lo + degradation * (p_hi - p_lo)
        if key == "temperature":
            temperature = round(_clamp(val * 0.9 + degraded * 0.1, p_lo, p_hi), 2)
        elif key == "vibration":
            vibration = round(_clamp(val * 0.85 + degraded * 0.15, p_lo, p_hi), 3)
        elif key == "pressure":
            pressure = round(_clamp(val * 0.9 + degraded * 0.1, p_lo, p_hi), 2)
        else:
            motor_current = round(_clamp(val * 0.9 + degraded * 0.1, p_lo, p_hi), 2)

    return {
        "temperature": temperature,
        "vibration": vibration,
        "pressure": pressure,
        "motor_current": motor_current,
        "health_indicator": round(health_pct, 2),
        "cycle": cycle,
        "unit": int(row["unit"]),
        "rul_cycles": rul_cycles,
        "rul_hours": round(float(row.get("rul_hours", rul_cycles * 10)), 1),
        "degradation_index": round(degradation, 4),
        "cmapss_sensors": {
            k: round(float(row[v]), 4) for k, v in SENSOR_MAP.items()
        },
    }


def build_training_frame(df: pd.DataFrame) -> pd.DataFrame:
    get_sensor_stats(df)
    df = compute_rul_labels(df)
    records = []
    for _, row in df.iterrows():
        row = row.copy()
        row["max_cycle"] = df[df["unit"] == row["unit"]]["cycle"].max()
        records.append(to_plant_features(row))
    return pd.DataFrame(records)


def get_unit_trajectory(df: pd.DataFrame, unit: int) -> pd.DataFrame:
    sub = df[df["unit"] == unit].sort_values("cycle").copy()
    sub = compute_rul_labels(sub)
    sub["max_cycle"] = sub["cycle"].max()
    return sub


def get_degrading_units(df: pd.DataFrame, n: int = 5) -> list[int]:
    lifetimes = df.groupby("unit")["cycle"].max().sort_values()
    return [int(u) for u in lifetimes.head(n).index.tolist()]
