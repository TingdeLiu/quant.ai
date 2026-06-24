from __future__ import annotations

from pathlib import Path

import yaml

from quant_agent.config import parse_config
from quant_agent.config_tools import write_recommended_config


def test_universe_can_be_loaded_from_csv(tmp_path: Path) -> None:
    universe_path = tmp_path / "universe.csv"
    universe_path.write_text("symbol,name\naapl,Apple\nMSFT,Microsoft\naapl,Duplicate\n", encoding="utf-8")
    config = parse_config(
        {
            "data": {
                "source": "csv",
                "csv_path": str(tmp_path / "prices.csv"),
                "cache_dir": "cache",
                "universe_path": str(universe_path),
            }
        },
        base=tmp_path,
    )
    assert config.data.universe == ["AAPL", "MSFT"]
    assert config.data.universe_path == universe_path


def test_evaluation_periods_are_parsed(tmp_path: Path) -> None:
    config = parse_config(
        {
            "data": {"source": "csv", "csv_path": str(tmp_path / "prices.csv"), "universe": ["SPY"]},
            "evaluation": {"periods": [{"name": "test", "start": "2024-01-01", "end": None}]},
        },
        base=tmp_path,
    )
    assert len(config.evaluation.periods) == 1
    assert config.evaluation.periods[0].name == "test"


def test_signal_weights_are_parsed(tmp_path: Path) -> None:
    config = parse_config(
        {
            "data": {"source": "csv", "csv_path": str(tmp_path / "prices.csv"), "universe": ["SPY"]},
            "strategy": {"signal_weights": {"momentum_12_1": 2, "low_volatility": 0.5}},
        },
        base=tmp_path,
    )
    assert config.strategy.signal_weights == {"momentum_12_1": 2.0, "low_volatility": 0.5}


def test_optimization_config_is_parsed(tmp_path: Path) -> None:
    config = parse_config(
        {
            "data": {"source": "csv", "csv_path": str(tmp_path / "prices.csv"), "universe": ["SPY"]},
            "optimization": {
                "enabled": False,
                "train_period": "fit",
                "validation_period": "select",
                "objective": "sortino",
                "max_drawdown_floor": -0.25,
                "walk_forward_enabled": True,
                "walk_forward_windows": [
                    {
                        "name": "wf",
                        "train_start": "2020-01-01",
                        "train_end": "2020-12-31",
                        "validation_start": "2021-01-01",
                        "validation_end": "2021-12-31",
                    }
                ],
            },
        },
        base=tmp_path,
    )
    assert not config.optimization.enabled
    assert config.optimization.train_period == "fit"
    assert config.optimization.validation_period == "select"
    assert config.optimization.objective == "sortino"
    assert config.optimization.max_drawdown_floor == -0.25
    assert config.optimization.walk_forward_enabled
    assert config.optimization.walk_forward_windows[0]["name"] == "wf"


def test_optional_roadmap_configs_are_parsed(tmp_path: Path) -> None:
    config = parse_config(
        {
            "data": {"source": "csv", "csv_path": str(tmp_path / "prices.csv"), "universe": ["SPY"]},
            "ml": {"enabled": True, "prediction_horizon_days": 10},
            "llm": {"enabled": True, "model": "test-model", "api_key_env": "TEST_API_KEY"},
            "paper_trading": {"enabled": True, "account_value": 123000, "max_order_notional": 12000},
            "dashboard": {
                "enabled": True,
                "output_path": "reports/current/dashboard.html",
                "service_dir": "reports/service",
                "runs_dir": "reports/runs",
            },
            "dashboard_security": {
                "enabled": True,
                "token_env": "TEST_DASHBOARD_TOKEN",
                "audit_log_path": "reports/dashboard_audit.jsonl",
            },
            "schedule": {"enabled": True, "interval_minutes": 60, "run_on_start": True},
            "alerts": {"enabled": True, "max_drawdown_floor": -0.2, "min_sharpe": 1.0, "max_stale_rows": 5},
            "notifications": {"enabled": True, "min_severity": "critical", "channels": ["file"]},
            "approvals": {"require_manual_paper_approval": True, "allow_broker_submit_after_approval": False},
        },
        base=tmp_path,
    )
    assert config.ml.enabled
    assert config.ml.prediction_horizon_days == 10
    assert config.llm.model == "test-model"
    assert config.paper_trading.account_value == 123000
    assert config.dashboard.output_path == tmp_path / "reports/current/dashboard.html"
    assert config.dashboard.service_dir == tmp_path / "reports/service"
    assert config.dashboard.runs_dir == tmp_path / "reports/runs"
    assert config.dashboard_security.enabled
    assert config.dashboard_security.token_env == "TEST_DASHBOARD_TOKEN"
    assert config.dashboard_security.audit_log_path == tmp_path / "reports/dashboard_audit.jsonl"
    assert config.schedule.enabled
    assert config.schedule.interval_minutes == 60
    assert config.schedule.run_on_start
    assert config.alerts.max_drawdown_floor == -0.2
    assert config.alerts.min_sharpe == 1.0
    assert config.notifications.min_severity == "critical"
    assert config.approvals.require_manual_paper_approval


def test_write_recommended_config(tmp_path: Path) -> None:
    base = tmp_path / "base.yaml"
    weights = tmp_path / "weights.json"
    output = tmp_path / "recommended.yaml"
    base.write_text(
        """
data:
  source: csv
  csv_path: prices.csv
  universe:
    - SPY
strategy:
  benchmark: SPY
  signal_weights:
    momentum_12_1: 1.0
""".strip(),
        encoding="utf-8",
    )
    weights.write_text('{"momentum_12_1": 0.5, "trend_20_50": 0.5}', encoding="utf-8")
    applied = write_recommended_config(base, weights, output)
    config = parse_config(yaml.safe_load(output.read_text(encoding="utf-8")), base=tmp_path)
    assert applied == {"momentum_12_1": 0.5, "trend_20_50": 0.5}
    assert config.strategy.signal_weights == applied
    assert config.report.output_dir == tmp_path / "reports/recommended"
