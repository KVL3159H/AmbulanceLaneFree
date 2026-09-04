"""Synthetic cardinal paths expressed as metre offsets from the junction centre."""

from __future__ import annotations

from ..core.models import Approach


def offset_for_side(side: Approach, signed_distance_metres: float) -> tuple[float, float, float]:
    """Return north/east offsets and travel heading; negative distance is past centre."""
    if side is Approach.NORTH:
        return signed_distance_metres, 0.0, 180.0
    if side is Approach.SOUTH:
        return -signed_distance_metres, 0.0, 0.0
    if side is Approach.EAST:
        return 0.0, signed_distance_metres, 270.0
    return 0.0, -signed_distance_metres, 90.0


def metres_to_coordinates(
    centre_latitude: float,
    centre_longitude: float,
    north_metres: float,
    east_metres: float,
) -> tuple[float, float]:
    latitude = centre_latitude + north_metres / 111_320.0
    longitude = centre_longitude + east_metres / (111_320.0 * __import__("math").cos(__import__("math").radians(centre_latitude)))
    return latitude, longitude
