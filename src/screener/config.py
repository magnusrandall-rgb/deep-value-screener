"""Single config loader + validation. Nothing else reads config.yaml directly.

Usage:
    from screener.config import load_config
    cfg = load_config()              # reads ./config.yaml
    cfg.price.pct_off_ath            # typed access
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

DEFAULT_CONFIG_PATH = Path(os.environ.get("SCREENER_CONFIG", "config.yaml"))


class _Section:
    """Thin attribute view over a config dict, with dotted access + .get()."""

    def __init__(self, data: dict):
        self._data = data or {}

    def __getattr__(self, name: str) -> Any:
        if name in self._data:
            v = self._data[name]
            return _Section(v) if isinstance(v, dict) else v
        raise AttributeError(f"config key '{name}' not found")

    def get(self, name: str, default=None):
        return self._data.get(name, default)

    def as_dict(self) -> dict:
        return self._data


@dataclass
class Config:
    raw: dict
    path: Path

    def __getattr__(self, name: str):
        # Delegate top-level sections (price, floor, quality, ...) to _Section.
        if name in self.__dict__.get("raw", {}):
            v = self.raw[name]
            return _Section(v) if isinstance(v, dict) else v
        raise AttributeError(f"config section '{name}' not found")

    # Convenience accessors used across the codebase ---------------------------
    @property
    def reporting_currency(self) -> str:
        return self.raw.get("reporting_currency", "USD")

    @property
    def enabled_regions(self) -> list[str]:
        regions = self.raw.get("universe", {}).get("regions", {})
        return [r for r, on in regions.items() if on]


def _validate(raw: dict, path: Path) -> None:
    required = ["price", "floor", "quality", "valuation", "universe", "write_up"]
    missing = [k for k in required if k not in raw]
    if missing:
        raise ValueError(f"{path}: missing required config sections: {missing}")

    engine = raw.get("write_up", {}).get("engine", "templated")
    if engine not in ("templated", "llm"):
        raise ValueError(f"write_up.engine must be 'templated' or 'llm', got '{engine}'")

    if raw["price"]["pct_off_ath"] <= 0:
        raise ValueError("price.pct_off_ath must be > 0")


def load_config(path: Optional[Path | str] = None) -> Config:
    p = Path(path) if path else DEFAULT_CONFIG_PATH
    if not p.exists():
        raise FileNotFoundError(f"config file not found: {p}")
    raw = yaml.safe_load(p.read_text()) or {}
    _validate(raw, p)
    return Config(raw=raw, path=p)
