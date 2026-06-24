from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import pandas as pd


class Broker(Protocol):
    def preview_orders(self, orders: pd.DataFrame) -> pd.DataFrame:
        """Return a broker-shaped preview without submitting orders."""

    def submit_orders(self, orders: pd.DataFrame) -> pd.DataFrame:
        """Submit orders. Production implementations must enforce explicit approval."""


@dataclass
class PaperBroker:
    allow_submit: bool = False
    audit_log: list[dict[str, object]] = field(default_factory=list)

    def preview_orders(self, orders: pd.DataFrame) -> pd.DataFrame:
        preview = orders.copy()
        preview["broker"] = "paper"
        preview["status"] = "preview"
        return preview

    def submit_orders(self, orders: pd.DataFrame) -> pd.DataFrame:
        if not self.allow_submit:
            raise PermissionError("PaperBroker submission requires allow_submit=True")
        submitted = orders.copy()
        submitted["broker"] = "paper"
        submitted["status"] = "submitted"
        self.audit_log.extend(submitted.to_dict(orient="records"))
        return submitted
