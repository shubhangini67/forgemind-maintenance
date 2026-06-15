from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


class LocalVectorStore:
    """File-backed vector store — no Qdrant required."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.points: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            self.points = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.points = []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.points), encoding="utf-8")

    def upsert(self, point_id: int, vector: list[float], payload: dict[str, Any]) -> None:
        entry = {"id": point_id, "vector": vector, "payload": payload}
        self.points = [p for p in self.points if p["id"] != point_id]
        self.points.append(entry)
        self._save()

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a)) or 1.0
        nb = math.sqrt(sum(x * x for x in b)) or 1.0
        return dot / (na * nb)

    def search(
        self,
        query_vector: list[float],
        limit: int = 5,
        document_type: str | None = None,
        equipment_type: str | None = None,
    ) -> list[dict[str, Any]]:
        results = []
        for point in self.points:
            payload = point["payload"]
            if document_type and payload.get("document_type") != document_type:
                continue
            if equipment_type and payload.get("equipment_type") != equipment_type:
                continue
            score = self._cosine(query_vector, point["vector"])
            results.append({"score": score, "payload": payload})
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]
