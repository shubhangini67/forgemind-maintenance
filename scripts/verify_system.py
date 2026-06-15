#!/usr/bin/env python3
"""Verify the full stack is working."""

import json
import sys
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8000"


def req(method: str, path: str, data: dict | None = None, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data else None
    r = urllib.request.Request(f"{BASE}{path}", data=body, headers=headers, method=method)
    with urllib.request.urlopen(r, timeout=120) as resp:
        return json.loads(resp.read())


def main() -> int:
    print("1. Health check...")
    health = req("GET", "/health")
    assert health["status"] == "healthy"
    assert "ml_models" in health
    print(f"   OK — ML MAE: {health['ml_models'].get('rul_mae_hours')}h")

    print("2. Login...")
    login_data = urllib.parse.urlencode({"username": "engineer@steelplant.com", "password": "demo1234"}).encode()
    r = urllib.request.Request(
        f"{BASE}/api/v1/auth/login",
        data=login_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(r) as resp:
        token = json.loads(resp.read())["access_token"]
    print("   OK")

    print("3. Dashboard...")
    dash = req("GET", "/api/v1/equipment/dashboard", token=token)
    assert dash["total_equipment"] >= 5
    print(f"   OK — {dash['total_equipment']} equipment, {dash['open_alerts']} alerts")

    print("4. Multi-agent chat...")
    chat = req(
        "POST",
        "/api/v1/chat",
        {"message": "RM-002 vibration high fault E-2041", "equipment_id": 2},
        token=token,
    )
    assert len(chat["agent_trace"]) >= 8
    assert chat["message"]
    print(f"   OK — {len(chat['agent_trace'])} agents, {len(chat.get('citations', []))} citations")

    print("5. Diagnosis...")
    diag = req(
        "POST",
        "/api/v1/diagnose",
        {"equipment_id": 2, "symptoms": "high vibration", "fault_codes": ["E-2041"]},
        token=token,
    )
    assert diag["confidence_score"] > 0
    print(f"   OK — confidence {diag['confidence_score']}, risk {diag['risk_level']}")

    print("\n=== ALL CHECKS PASSED ===")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"\nFAILED: {exc}")
        sys.exit(1)
