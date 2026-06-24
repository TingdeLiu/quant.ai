from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pandas as pd

from quant_agent.config import DataConfig
from quant_agent.data import load_prices


class DataAdapter(Protocol):
    def load_prices(self, config: DataConfig) -> pd.DataFrame:
        """Load normalized daily OHLCV prices."""


@dataclass(frozen=True)
class LocalDataAdapter:
    def load_prices(self, config: DataConfig) -> pd.DataFrame:
        return load_prices(config)


@dataclass(frozen=True)
class YFinanceDataAdapter:
    def load_prices(self, config: DataConfig) -> pd.DataFrame:
        return load_prices(config)


@dataclass(frozen=True)
class AlpacaDataAdapter:
    def load_prices(self, config: DataConfig) -> pd.DataFrame:
        raise NotImplementedError("Alpaca data adapter is reserved for a future authenticated integration.")


@dataclass(frozen=True)
class PolygonDataAdapter:
    def load_prices(self, config: DataConfig) -> pd.DataFrame:
        raise NotImplementedError("Polygon data adapter is reserved for a future authenticated integration.")
