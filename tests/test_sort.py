from datetime import date
from unittest.mock import MagicMock

import requests

from pse_data_scraper.client import PSEClient
from pse_data_scraper.downloader import fetch_historical_data
from pse_data_scraper.models import Company


def _make_company() -> Company:
    return Company(company_id="1", security_id="2", company_name="Test", stock_symbol="TST")


def _mock_client(response_json: dict) -> PSEClient:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = 200
    resp.json.return_value = response_json
    resp.raise_for_status = MagicMock()

    client = PSEClient(rate_limit_seconds=0.0)
    client.post = MagicMock(return_value=resp)
    return client


def test_fetch_historical_data_returns_sorted_by_date():
    data = {
        "chartData": [
            {
                "CHART_DATE": "Jan 15, 2024 00:00:00",
                "VALUE": 3,
                "OPEN": 3,
                "CLOSE": 3,
                "HIGH": 3,
                "LOW": 3,
            },
            {
                "CHART_DATE": "Jan 02, 2024 00:00:00",
                "VALUE": 1,
                "OPEN": 1,
                "CLOSE": 1,
                "HIGH": 1,
                "LOW": 1,
            },
            {
                "CHART_DATE": "Jan 10, 2024 00:00:00",
                "VALUE": 2,
                "OPEN": 2,
                "CLOSE": 2,
                "HIGH": 2,
                "LOW": 2,
            },
        ]
    }
    client = _mock_client(data)
    company = _make_company()
    results = fetch_historical_data(client, company, "01-01-2024", "01-31-2024")

    dates = [r.date for r in results]
    assert dates == sorted(dates), f"Dates not sorted: {dates}"
    assert dates == [date(2024, 1, 2), date(2024, 1, 10), date(2024, 1, 15)]


def test_fetch_historical_data_sorted_with_empty():
    """Empty results should not break on sort."""
    client = _mock_client({"chartData": []})
    company = _make_company()
    results = fetch_historical_data(client, company, "01-01-2024", "01-31-2024")

    assert results == []
