"""Approach-side classification from a junction-to-vehicle bearing."""

from __future__ import annotations

from .models import Approach


def detect_approach(relative_bearing_degrees: float) -> Approach:
    bearing = relative_bearing_degrees % 360.0
    if bearing >= 315.0 or bearing < 45.0:
        return Approach.NORTH
    if bearing < 135.0:
        return Approach.EAST
    if bearing < 225.0:
        return Approach.SOUTH
    return Approach.WEST
