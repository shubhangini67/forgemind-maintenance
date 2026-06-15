#!/usr/bin/env python3
"""Simulate IoT sensor stream for demo."""

import asyncio
import random
import sys
from datetime import datetime, timezone

import httpx

API = "http://localhost:8000/api/v1"
EMAIL = "engineer@steelplant.com"
PASSWORD = "demo1234"


async def get_token(client: httpx.AsyncClient) -> str:
    resp = await client.post(
        f"{API}/auth/login",
        data={"username": EMAIL, "password": PASSWORD},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


async def simulate(equipment_id: int = 2, interval: float = 5.0) -> None:
    rng = random.Random()
    async with httpx.AsyncClient(timeout=30) as client:
        token = await get_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        tick = 0
        while True:
            tick += 1
            anomaly = tick > 10 and rng.random() > 0.6
            payload = {
                "equipment_id": equipment_id,
                "temperature": 70 + tick * 0.5 + (20 if anomaly else 0),
                "vibration": 3 + tick * 0.1 + (7 if anomaly else 0),
                "pressure": 110 + tick * 0.2,
                "motor_current": 55 + tick * 0.15,
                "health_indicator": max(25, 95 - tick * 2 - (15 if anomaly else 0)),
            }
            resp = await client.post(
                f"{API}/equipment/{equipment_id}/sensors",
                json=payload,
                headers=headers,
            )
            print(f"[{datetime.now(timezone.utc).isoformat()}] tick={tick} status={resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                print(f"  sensor_id={data.get('id')} health={payload['health_indicator']}")
            await asyncio.sleep(interval)


if __name__ == "__main__":
    eq_id = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    asyncio.run(simulate(eq_id))
