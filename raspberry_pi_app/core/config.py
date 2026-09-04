"""Typed access to the junction YAML configuration."""

from __future__ import annotations

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
    return Path(__file__).resolve().parents[2] / "config" / "junction.yaml"


def load_config(path: str | Path | None = None) -> JunctionConfig:
    source = Path(path) if path else default_config_path()
    with source.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    required = {"junction", "detection", "timing", "mqtt", "simulation"}
    missing = required.difference(data or {})
    if missing:
        raise ValueError(f"Configuration sections missing: {', '.join(sorted(missing))}")
    return JunctionConfig(data, source)
