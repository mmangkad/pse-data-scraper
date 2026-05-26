from datetime import date
from decimal import Decimal

from pse_data_scraper.models import HistoricalPrice


def test_from_api_parses_numeric_fields_as_decimal():
    payload = {
        "CHART_DATE": "Jan 02, 2024 00:00:00",
        "VALUE": 99270190.0,
        "OPEN": 685.0,
        "CLOSE": 715.0,
        "HIGH": 715.0,
        "LOW": 685.0,
    }
    result = HistoricalPrice.from_api(payload, "AC")

    assert result is not None
    assert isinstance(result.open, Decimal)
    assert isinstance(result.close, Decimal)
    assert isinstance(result.value, Decimal)
    assert result.open == Decimal("685.0")
    assert result.close == Decimal("715")


def test_from_api_returns_none_on_bad_date():
    payload = {
        "CHART_DATE": "not-a-date",
        "VALUE": 1,
        "OPEN": 1,
        "CLOSE": 1,
        "HIGH": 1,
        "LOW": 1,
    }
    result = HistoricalPrice.from_api(payload, "TST")
    assert result is None


def test_from_api_returns_none_on_missing_key():
    payload = {"CHART_DATE": "Jan 02, 2024 00:00:00"}
    result = HistoricalPrice.from_api(payload, "TST")
    assert result is None
