"""
Data models for PSE EDGE responses.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date
from typing import Mapping, Optional


CHART_DATE_FORMAT = "%b %d, %Y %H:%M:%S"


@dataclass(frozen=True)
class Company:
    company_id: str
    security_id: str
    company_name: str
    stock_symbol: str


@dataclass(frozen=True)
class HistoricalPrice:
    date: date
    symbol: str
    value: str
    open: str
    close: str
    high: str
    low: str

    @classmethod
    def from_api(cls, payload: Mapping[str, str], symbol: str) -> Optional["HistoricalPrice"]:
        try:
            chart_date = payload["CHART_DATE"]
            parsed_date = datetime.strptime(chart_date, CHART_DATE_FORMAT).date()
            return cls(
                date=parsed_date,
                symbol=symbol,
                value=str(payload["VALUE"]),
                open=str(payload["OPEN"]),
                close=str(payload["CLOSE"]),
                high=str(payload["HIGH"]),
                low=str(payload["LOW"]),
            )
        except (KeyError, ValueError):
            return None
