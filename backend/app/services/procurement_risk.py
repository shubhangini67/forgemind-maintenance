"""Shared spare / procurement profile for risk scoring."""

from __future__ import annotations

from typing import Any


def spare_procurement_profile(spares: list[dict[str, Any]]) -> dict[str, Any]:
    """Worst-case spare line drives procurement risk (lowest stock, longest lead)."""
    if not spares:
        return {
            "spare_stock": 0,
            "lead_time_days": 14,
            "reorder_level": 5,
            "critical_part_number": None,
            "critical_part_name": None,
        }
    critical = min(spares, key=lambda s: s.get("quantity_available", 0))
    return {
        "spare_stock": int(critical.get("quantity_available", 0)),
        "lead_time_days": int(max(s.get("lead_time_days", 14) for s in spares)),
        "reorder_level": int(critical.get("reorder_level", 5)),
        "critical_part_number": critical.get("part_number"),
        "critical_part_name": critical.get("name"),
    }
