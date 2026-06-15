"""Asset dependency graph — multi-hop cascade for failure scenario analysis."""

from __future__ import annotations

from collections import deque

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.fleet import DEFAULT_DEPENDENCIES, PRODUCTION_RATE_TPH
from app.models import Equipment, EquipmentDependency


async def load_dependency_edges(db: AsyncSession) -> list[dict]:
    """Load dependency edges from DB; returns list of dicts with equipment codes."""
    eq_result = await db.execute(select(Equipment))
    equipment_by_id = {eq.id: eq for eq in eq_result.scalars().all()}

    dep_result = await db.execute(select(EquipmentDependency))
    edges: list[dict] = []
    for dep in dep_result.scalars().all():
        up = equipment_by_id.get(dep.upstream_equipment_id)
        down = equipment_by_id.get(dep.downstream_equipment_id)
        if not up or not down:
            continue
        edges.append({
            "upstream_code": up.equipment_code,
            "downstream_code": down.equipment_code,
            "downstream_name": down.name,
            "dependency_type": dep.dependency_type,
            "impact_weight": dep.impact_weight,
            "production_share_pct": dep.production_share_pct,
            "description": dep.description or "",
            "downstream_criticality": down.criticality,
        })
    return edges


def _edges_from_defaults() -> list[dict]:
    return [
        {
            "upstream_code": d["upstream"],
            "downstream_code": d["downstream"],
            "dependency_type": d["type"],
            "impact_weight": d["weight"],
            "production_share_pct": d["share_pct"],
            "description": d["desc"],
        }
        for d in DEFAULT_DEPENDENCIES
    ]


def build_adjacency(edges: list[dict]) -> dict[str, list[dict]]:
    adj: dict[str, list[dict]] = {}
    for e in edges:
        adj.setdefault(e["upstream_code"], []).append(e)
    return adj


def compute_cascade(
    source_code: str,
    edges: list[dict],
    downtime_hours: float,
    max_depth: int = 4,
) -> list[dict]:
    """Multi-hop BFS cascade — each hop attenuates impact by edge weight."""
    adj = build_adjacency(edges)
    visited: set[str] = {source_code}
    queue: deque[tuple[str, int, float]] = deque([(source_code, 0, 1.0)])
    affected: list[dict] = []

    while queue:
        code, depth, cumulative = queue.popleft()
        if depth >= max_depth:
            continue
        for edge in adj.get(code, []):
            down = edge["downstream_code"]
            if down in visited:
                continue
            visited.add(down)
            weight = float(edge.get("impact_weight", 0.8))
            share = float(edge.get("production_share_pct", 50)) / 100.0
            hop_impact = cumulative * weight
            prod_rate = PRODUCTION_RATE_TPH.get(down, 0.0)
            production_loss = round(downtime_hours * prod_rate * share * hop_impact, 1)
            affected.append({
                "equipment_code": down,
                "equipment_name": edge.get("downstream_name", down),
                "hop": depth + 1,
                "dependency_type": edge.get("dependency_type", "process_flow"),
                "impact_score": round(hop_impact, 2),
                "production_share_pct": edge.get("production_share_pct", 50),
                "estimated_downtime_hours": round(downtime_hours * hop_impact, 1),
                "production_loss_tons": production_loss,
                "description": edge.get("description", ""),
                "severity": _severity(hop_impact),
            })
            queue.append((down, depth + 1, hop_impact))

    affected.sort(key=lambda a: a["impact_score"], reverse=True)
    return affected


def aggregate_impact(
    source_code: str,
    source_downtime_hours: float,
    source_downtime_cost_per_day: float,
    source_criticality: int,
    affected: list[dict],
) -> dict:
    """Roll up production, downtime, and financial impact across cascade."""
    source_prod = PRODUCTION_RATE_TPH.get(source_code, 0.0) * source_downtime_hours
    cascade_prod = sum(a.get("production_loss_tons", 0) for a in affected)
    cascade_downtime = sum(a.get("estimated_downtime_hours", 0) for a in affected)
    total_downtime = source_downtime_hours + cascade_downtime * 0.3  # partial parallel outages

    direct_cost = int(source_downtime_cost_per_day * source_downtime_hours / 24)
    cascade_cost = int(direct_cost * 0.45 * len(affected))  # downstream revenue at risk
    penalty = int(cascade_prod * 8500)  # INR per ton hot metal equivalent
    total_cost = direct_cost + cascade_cost + penalty

    return {
        "source_downtime_hours": round(source_downtime_hours, 1),
        "cascade_downtime_hours": round(cascade_downtime, 1),
        "total_downtime_hours": round(total_downtime, 1),
        "source_production_loss_tons": round(source_prod, 1),
        "cascade_production_loss_tons": round(cascade_prod, 1),
        "total_production_loss_tons": round(source_prod + cascade_prod, 1),
        "direct_cost_inr": direct_cost,
        "cascade_cost_inr": cascade_cost,
        "penalty_inr": penalty,
        "total_cost_inr": total_cost,
        "criticality_multiplier": source_criticality,
    }


def _severity(impact: float) -> str:
    if impact >= 0.75:
        return "critical"
    if impact >= 0.5:
        return "high"
    if impact >= 0.25:
        return "medium"
    return "low"


async def get_dependency_graph(db: AsyncSession) -> dict:
    """Full graph for UI visualization."""
    edges = await load_dependency_edges(db)
    if not edges:
        edges = _edges_from_defaults()

    nodes = {}
    for e in edges:
        for code, role in [(e["upstream_code"], "upstream"), (e["downstream_code"], "downstream")]:
            if code not in nodes:
                nodes[code] = {"code": code, "production_rate_tph": PRODUCTION_RATE_TPH.get(code, 0)}

    return {"nodes": list(nodes.values()), "edges": edges}
