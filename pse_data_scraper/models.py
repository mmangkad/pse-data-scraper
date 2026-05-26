"""
Data models for PSE EDGE responses.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
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
    value: Decimal
    open: Decimal
    close: Decimal
    high: Decimal
    low: Decimal

    @classmethod
    def from_api(cls, payload: Mapping[str, object], symbol: str) -> Optional["HistoricalPrice"]:
        try:
            chart_date = payload["CHART_DATE"]
            parsed_date = datetime.strptime(chart_date, CHART_DATE_FORMAT).date()
            return cls(
                date=parsed_date,
                symbol=symbol,
                value=Decimal(str(payload["VALUE"])),
                open=Decimal(str(payload["OPEN"])),
                close=Decimal(str(payload["CLOSE"])),
                high=Decimal(str(payload["HIGH"])),
                low=Decimal(str(payload["LOW"])),
            )
        except (KeyError, ValueError, InvalidOperation):
            return None
