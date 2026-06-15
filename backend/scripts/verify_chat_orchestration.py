"""Verify chat returns full agent orchestration panel."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8000"


def post_form(path: str, fields: dict[str, str]) -> dict:
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def post_json(path: str, body: dict, token: str | None = None) -> dict:
    data = json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def main() -> int:
    try:
        auth = post_form(
            "/api/v1/auth/login",
            {"username": "engineer@steelplant.com", "password": "demo1234"},
        )
    except urllib.error.HTTPError as e:
        print("LOGIN FAILED:", e.read().decode()[:500])
        return 1

    token = auth.get("access_token")
    if not token:
        print("No access token:", auth)
        return 1

    chat = post_json(
        "/api/v1/chat",
        {
            "message": "What is today's date?",
            "equipment_id": 1,
        },
        token=token,
    )

    rp = chat.get("reasoning_panel") or {}
    steps = [s.get("agent") for s in rp.get("steps", [])]
    msg = chat.get("message") or ""
    if steps and any(a not in ("supervisor",) for a in steps if a != "supervisor"):
        print("FAIL: date question triggered maintenance agents:", steps)
        return 1
    if "Today is" not in msg:
        print("FAIL: date answer missing. message:", msg[:200])
        return 1
    print("OK: conversational date query — no agents, direct answer")

    chat = post_json(
        "/api/v1/chat",
        {
            "message": "What is the operational risk for this asset?",
            "equipment_id": 1,
        },
        token=token,
    )

    rp = chat.get("reasoning_panel") or {}
    steps = [s.get("agent") for s in rp.get("steps", [])]
    exp = (chat.get("structured_output") or {}).get("explainability") or {}
    print("risk intent:", exp.get("routing_log", {}).get("detected_intent"))
    print("risk template:", exp.get("response_template"))
    print("risk agents:", steps)
    if "production_impact_agent" not in steps and "risk_agent" not in steps:
        print("WARN: risk query may need production/risk agents")

    chat = post_json(
        "/api/v1/chat",
        {"message": "Rank all assets by remaining useful life", "equipment_id": 1},
        token=token,
    )
    exp = (chat.get("structured_output") or {}).get("explainability") or {}
    print("ranking template:", exp.get("response_template"))
    if exp.get("response_template") != "asset_ranking":
        print("FAIL: expected asset_ranking template")
        return 1
    ranking = exp.get("asset_ranking") or {}
    if len(ranking.get("ranked_assets") or []) < 2:
        print("FAIL: expected fleet ranking rows")
        return 1
    print("OK: asset ranking intent")

    chat = post_json(
        "/api/v1/chat",
        {"message": "How much production loss if BF-001 fails now?", "equipment_id": 1},
        token=token,
    )
    exp = (chat.get("structured_output") or {}).get("explainability") or {}
    if exp.get("response_template") != "business_impact":
        print("FAIL: expected business_impact template, got", exp.get("response_template"))
        return 1
    print("OK: business impact intent")

    chat = post_json(
        "/api/v1/chat",
        {"message": "Which spare parts are critical?", "equipment_id": 1},
        token=token,
    )
    exp = (chat.get("structured_output") or {}).get("explainability") or {}
    if exp.get("response_template") != "critical_spares":
        print("FAIL: expected critical_spares template")
        return 1
    print("OK: critical spares intent")

    chat = post_json(
        "/api/v1/chat",
        {
            "message": "What happens if maintenance is delayed by 7 days?",
            "equipment_id": 1,
        },
        token=token,
    )
    exp = (chat.get("structured_output") or {}).get("explainability") or {}
    sim = exp.get("scenario_simulation") or (chat.get("structured_output") or {}).get("scenario_simulation") or {}
    projections = sim.get("projections") or []
    msg = chat.get("message") or ""
    print("scenario projections:", len(projections))
    print("message has table:", "| Scenario |" in msg)
    if len(projections) < 4:
        print("FAIL: expected 4 deferral horizons (+1/+3/+7/+14 days)")
        return 1
    if "| Scenario |" not in msg:
        print("FAIL: response missing scenario markdown table")
        return 1
    if "### Predictive Agent" in msg:
        print("FAIL: failure simulation must not include predictive agent summary")
        return 1
    if "Failure Scenario Simulation" not in msg:
        print("FAIL: missing failure simulation header")
        return 1
    steps = [s.get("agent") for s in (chat.get("reasoning_panel") or {}).get("steps", [])]
    if "scenario_agent" not in steps:
        print("FAIL: scenario_agent not in reasoning panel:", steps)
        return 1
    if "predictive_agent" in steps:
        print("FAIL: predictive_agent should not run for failure simulation")
        return 1
    print("OK: failure scenario simulation with markdown table")
    return 0


if __name__ == "__main__":
    sys.exit(main())
