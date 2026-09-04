"""Noise-resistant ETA calculations."""

from __future__ import annotations

from statistics import median
from typing import Iterable


def filtered_speed(speeds_mps: Iterable[float]) -> float:
    values = [max(0.0, float(value)) for value in speeds_mps]
    return median(values) if values else 0.0


def calculate_eta(
    distance_metres: float,
    speeds_mps: Iterable[float],
    *,
    immediate: bool = False,
    minimum_assumed_speed_mps: float = 2.0,
) -> tuple[float | None, float]:
    speed = filtered_speed(speeds_mps)
    if speed < 0.5:
        if not immediate:
            return None, speed
        speed = minimum_assumed_speed_mps
    return max(0.0, distance_metres) / max(speed, 0.1), speed
