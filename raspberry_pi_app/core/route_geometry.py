"""Polyline progress and laboratory junction geometry, in local metre coordinates."""
from __future__ import annotations

import math
from dataclasses import dataclass

from .models import Approach


def local_point(latitude, longitude, centre_latitude, centre_longitude):
    return ((longitude - centre_longitude) * 111_320 * math.cos(math.radians(centre_latitude)),
            (latitude - centre_latitude) * 111_320)


@dataclass(frozen=True)
class Projection:
    progress: float
    lateral: float
    heading: float
    total: float


def project_polyline(point, path) -> Projection:
    if len(path) < 2:
        raise ValueError("route requires at least two points")
    best = None
    total = 0.0
    for a, b in zip(path, path[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length == 0:
            continue
        t = max(0.0, min(1.0, ((point[0]-a[0])*dx + (point[1]-a[1])*dy) / length**2))
        lateral = math.hypot(point[0]-a[0]-t*dx, point[1]-a[1]-t*dy)
        candidate = (lateral, total + t*length, math.degrees(math.atan2(dx, dy)) % 360)
        if best is None or candidate[0] < best[0]:
            best = candidate
        total += length
    if best is None:
        raise ValueError("route contains no nonzero segment")
    return Projection(best[1], best[0], best[2], total)


def inside_polygon(point, polygon):
    inside = False
    x, y = point
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > y) != (b[1] > y):
            if x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1]) + a[0]:
                inside = not inside
    return inside

def point_along_path(path,progress):
    remaining=max(0,progress)
    for a,b in zip(path,path[1:]):
        length=math.dist(a,b)
        if length<=0: continue
        if remaining<=length:
            fraction=remaining/length
            return a[0]+(b[0]-a[0])*fraction,a[1]+(b[1]-a[1])*fraction,math.degrees(math.atan2(b[0]-a[0],b[1]-a[1]))%360
        remaining-=length
    a,b=path[-2:]
    return b[0],b[1],math.degrees(math.atan2(b[0]-a[0],b[1]-a[1]))%360


def lab_path(side: Approach, extent=1200.0):
    # Inbound side, NOT travel heading. Left-hand model lanes.
    return {
        Approach.NORTH: [(-4, extent), (-4, -extent)],
        Approach.EAST: [(extent, 4), (-extent, 4)],
        Approach.SOUTH: [(4, -extent), (4, extent)],
        Approach.WEST: [(-extent, -4), (extent, -4)],
    }[side]


def passage_geometry(config, packet, side):
    geometry = config.raw.get("geometry", {})
    extent = float(geometry.get("route_extent_metres", 1200))
    half = float(geometry.get("junction_half_width_metres", 20))
    point = local_point(packet.latitude, packet.longitude,
                        float(config.junction["latitude"]), float(config.junction["longitude"]))
    path = geometry.get("paths", {}).get(side.value, lab_path(side, extent))
    projection = project_polyline(point, path)
    stop = float(geometry.get("stop_progress", {}).get(side.value, extent-half))
    exit_progress = float(geometry.get("exit_progress", {}).get(side.value, extent+half))
    polygon = geometry.get("polygon", [[-half,-half],[half,-half],[half,half],[-half,half]])
    return projection, stop-projection.progress, projection.progress-exit_progress, inside_polygon(point, polygon)
