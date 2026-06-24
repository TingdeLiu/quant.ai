from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


def write_recommended_config(
    base_config_path: Path,
    weights_path: Path,
    output_path: Path,
    report_output_dir: str | None = "reports/recommended",
) -> dict[str, float]:
    with base_config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    with weights_path.open("r", encoding="utf-8") as f:
        weights = json.load(f)
    normalized_weights = {str(key): float(value) for key, value in weights.items()}
    strategy = _section(config, "strategy")
    strategy["signal_weights"] = normalized_weights
    if report_output_dir is not None:
        report = _section(config, "report")
        report["output_dir"] = report_output_dir
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False, allow_unicode=True)
    return normalized_weights


def _section(config: dict[str, Any], name: str) -> dict[str, Any]:
    value = config.get(name)
    if not isinstance(value, dict):
        value = {}
        config[name] = value
    return value
