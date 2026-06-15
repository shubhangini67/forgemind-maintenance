"""Canonical 5-asset steel plant fleet — each maps 1:1 to NASA C-MAPSS FD001 engine unit."""

CANONICAL_FLEET = [
    {
        "code": "BF-001",
        "name": "Blast Furnace Blower",
        "equipment_type": "blast_furnace_blower",
        "location": "Blast Furnace Area",
        "criticality": 5,
        "cmapss_unit": 1,
    },
    {
        "code": "RM-002",
        "name": "Rolling Mill Motor",
        "equipment_type": "rolling_mill_motor",
        "location": "Hot Rolling Mill",
        "criticality": 5,
        "cmapss_unit": 2,
    },
    {
        "code": "CP-003",
        "name": "Coke Oven Compressor",
        "equipment_type": "coke_compressor",
        "location": "Coke Oven Battery",
        "criticality": 4,
        "cmapss_unit": 3,
    },
    {
        "code": "CW-004",
        "name": "Cooling Water Pump",
        "equipment_type": "cooling_pump",
        "location": "Utilities",
        "criticality": 3,
        "cmapss_unit": 4,
    },
    {
        "code": "CN-005",
        "name": "Continuous Caster Drive",
        "equipment_type": "caster_drive",
        "location": "Casting Line",
        "criticality": 5,
        "cmapss_unit": 5,
    },
]

CANONICAL_CODES = [a["code"] for a in CANONICAL_FLEET]

CODE_TO_CMAPSS = {a["code"]: a["cmapss_unit"] for a in CANONICAL_FLEET}

# Hot metal / coil production rate (tons per hour) used for scenario impact modelling
PRODUCTION_RATE_TPH: dict[str, float] = {
    "BF-001": 450.0,
    "RM-002": 280.0,
    "CP-003": 120.0,
    "CW-004": 0.0,   # utility — no direct production
    "CN-005": 180.0,
}

# Default process-flow dependencies (seeded into equipment_dependencies table)
DEFAULT_DEPENDENCIES: list[dict] = [
    {"upstream": "BF-001", "downstream": "RM-002", "type": "process_flow", "weight": 0.95, "share_pct": 85, "desc": "Blast furnace air supply to hot rolling mill"},
    {"upstream": "BF-001", "downstream": "CP-003", "type": "process_flow", "weight": 0.70, "share_pct": 40, "desc": "Shared utilities from blast furnace area"},
    {"upstream": "RM-002", "downstream": "CP-003", "type": "process_flow", "weight": 0.60, "share_pct": 35, "desc": "Rolling mill coke oven gas compression dependency"},
    {"upstream": "CP-003", "downstream": "CW-004", "type": "utility", "weight": 0.80, "share_pct": 60, "desc": "Compressor cooling water loop"},
    {"upstream": "CW-004", "downstream": "CN-005", "type": "utility", "weight": 0.90, "share_pct": 75, "desc": "Caster drive cooling water supply"},
    {"upstream": "RM-002", "downstream": "CN-005", "type": "process_flow", "weight": 0.55, "share_pct": 30, "desc": "Hot strip feed to continuous caster line"},
]
