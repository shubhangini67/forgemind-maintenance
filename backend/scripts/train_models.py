#!/usr/bin/env python3
"""Train ML models and print metrics."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.ml.predictive_engine import get_pm_engine


def main() -> None:
    engine = get_pm_engine()
    if not engine.train_metrics:
        metrics = engine.train_from_synthetic()
    else:
        metrics = engine.train_metrics
    print("=== ML Training Complete ===")
    for key, value in metrics.items():
        print(f"  {key}: {value}")
    print(f"\nModels saved to: {engine.model_dir}")


if __name__ == "__main__":
    main()
