"""Typed access to the junction YAML configuration."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class JunctionConfig:
    raw: dict[str, Any]
    source: Path

    @property
    def junction(self) -> dict[str, Any]:
        return self.raw["junction"]

    @property
    def detection(self) -> dict[str, Any]:
        return self.raw["detection"]

    @property
    def timing(self) -> dict[str, Any]:
        return self.raw["timing"]

    @property
    def mqtt(self) -> dict[str, Any]:
        return self.raw["mqtt"]

    @property
    def simulation(self) -> dict[str, Any]:
        return self.raw["simulation"]

    @property
    def authorized_ids(self) -> set[str]:
        return set(self.raw.get("security", {}).get("authorized_ambulance_ids", []))


def default_config_path() -> Path:
    candidates = [
        Path(__file__).resolve().parents[2] / "config" / "junction.yaml",
        Path(__file__).resolve().parents[1] / "config" / "junction.yaml",
        Path(getattr(sys, "_MEIPASS", "")) / "config" / "junction.yaml",
        Path.cwd() / "config" / "junction.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


def load_config(path: str | Path | None = None) -> JunctionConfig:
    source = Path(path) if path else default_config_path()
    with source.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    required = {"junction", "detection", "timing", "mqtt", "simulation"}
    missing = required.difference(data or {})
    if missing:
        raise ValueError(f"Configuration sections missing: {', '.join(sorted(missing))}")
    import math
    for field in ("normal_green_seconds", "minimum_green_seconds", "yellow_seconds",
                  "all_red_seconds", "maximum_ambulance_green_seconds"):
        value = data["timing"].get(field)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"Invalid positive signal duration: {field}")
    if data["timing"]["minimum_green_seconds"] > data["timing"]["normal_green_seconds"]:
        raise ValueError("minimum green cannot exceed normal green")
    mode = data["timing"].get("normal_cycle_mode", "SINGLE")
    if mode not in {"SINGLE", "PAIRED"}:
        raise ValueError("normal_cycle_mode must be SINGLE or PAIRED")
    if mode == "PAIRED" and not data["timing"].get("paired_movements", False):
        raise ValueError("paired movements require an explicitly compatible physical model")
    return JunctionConfig(data, source)
