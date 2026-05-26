import csv
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest

from pse_data_scraper.client import PSEClient
from pse_data_scraper.downloader import (
    download_historical_data,
    fetch_historical_data,
    write_company_history_csv,
)
from pse_data_scraper.models import Company, HistoricalPrice


def _read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open("r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
    return rows[0], rows[1:]


def test_write_company_history_csv_includes_company_column(tmp_path: Path):
    company = Company(company_id="1", security_id="2", company_name="BDO Unibank, Inc.", stock_symbol="BDO")
    rows = [
        HistoricalPrice(date=date(2024, 1, 2), symbol="BDO", value=Decimal("100"), open=Decimal("10"), close=Decimal("11"), high=Decimal("12"), low=Decimal("9")),
        HistoricalPrice(date=date(2024, 1, 3), symbol="BDO", value=Decimal("200"), open=Decimal("11"), close=Decimal("12"), high=Decimal("13"), low=Decimal("10")),
    ]

    output_path = tmp_path / "BDO_BDO_Unibank,_Inc.csv"
    write_company_history_csv(output_path, company, rows)

    header, data = _read_csv(output_path)
    assert header == ["Symbol", "Company", "Date", "Value", "Open", "Close", "High", "Low"]
    assert data[0][1] == "BDO Unibank, Inc."
    assert data[1][1] == "BDO Unibank, Inc."
    assert data[0][0] == "BDO"


def test_write_company_history_csv_creates_parent_dirs(tmp_path: Path):
    company = Company(company_id="1", security_id="2", company_name="Test", stock_symbol="TST")
    output_path = tmp_path / "nested" / "dir" / "TST_Test.csv"

    write_company_history_csv(output_path, company, [])

    header, data = _read_csv(output_path)
    assert header == ["Symbol", "Company", "Date", "Value", "Open", "Close", "High", "Low"]
    assert data == []


def test_fetch_historical_data_parses_chart_data(make_company, mock_client):
    data = {
        "chartData": [
            {
                "CHART_DATE": "Jan 02, 2024 00:00:00",
                "VALUE": 100.0,
                "OPEN": 10.0,
                "CLOSE": 11.0,
                "HIGH": 12.0,
                "LOW": 9.0,
            }
        ]
    }
    client = mock_client(data)
    company = make_company()
    results = fetch_historical_data(client, company, "01-01-2024", "01-31-2024")

    assert len(results) == 1
    assert results[0].symbol == "TST"
    assert results[0].date == date(2024, 1, 2)


def test_fetch_historical_data_caches_nonempty_response(tmp_path: Path, make_company, mock_client):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    data = {
        "chartData": [
            {
                "CHART_DATE": "Jan 02, 2024 00:00:00",
                "VALUE": 100.0,
                "OPEN": 10.0,
                "CLOSE": 11.0,
                "HIGH": 12.0,
                "LOW": 9.0,
            }
        ]
    }
    client = mock_client(data)
    company = make_company()
    fetch_historical_data(client, company, "01-01-2024", "01-31-2024", cache_dir=cache_dir)

    cache_files = list(cache_dir.glob("*.json"))
    assert len(cache_files) == 1
    with cache_files[0].open() as f:
        assert json.load(f) == data


def test_fetch_historical_data_does_not_cache_empty_response(tmp_path: Path, make_company, mock_client):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    data = {"chartData": []}

    client = mock_client(data)
    company = make_company()
    fetch_historical_data(client, company, "01-01-2024", "01-31-2024", cache_dir=cache_dir)

    cache_files = list(cache_dir.glob("*.json"))
    assert len(cache_files) == 0


def test_fetch_historical_data_skips_malformed_records(make_company, mock_client):
    data = {
        "chartData": [
            {"CHART_DATE": "not-a-date", "VALUE": 1, "OPEN": 1, "CLOSE": 1, "HIGH": 1, "LOW": 1},
            {"CHART_DATE": "Jan 02, 2024 00:00:00", "VALUE": 100.0, "OPEN": 10.0, "CLOSE": 11.0, "HIGH": 12.0, "LOW": 9.0},
        ]
    }
    client = mock_client(data)
    company = make_company()
    results = fetch_historical_data(client, company, "01-01-2024", "01-31-2024")

    assert len(results) == 1
    assert results[0].date == date(2024, 1, 2)


def test_fetch_historical_data_with_refresh_ignores_cache(tmp_path: Path, make_company, mock_client):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    data = {
        "chartData": [
            {
                "CHART_DATE": "Jan 02, 2024 00:00:00",
                "VALUE": 100.0,
                "OPEN": 10.0,
                "CLOSE": 11.0,
                "HIGH": 12.0,
                "LOW": 9.0,
            }
        ]
    }
    client = mock_client(data)
    company = make_company()

    # First call writes cache
    fetch_historical_data(client, company, "01-01-2024", "01-31-2024", cache_dir=cache_dir)
    assert len(list(cache_dir.glob("*.json"))) == 1

    # Second call with refresh=True should still make a request (cache ignored)
    fetch_historical_data(client, company, "01-01-2024", "01-31-2024", cache_dir=cache_dir, refresh=True)
    assert client.post.call_count == 2


def test_download_historical_data_raises_without_companies_or_csv():
    client = PSEClient(rate_limit_seconds=0.0)
    with pytest.raises(ValueError, match="Either 'companies' or 'input_csv'"):
        download_historical_data(client=client)


def test_download_historical_data_prefers_companies_over_csv(tmp_path):
    """When both companies and input_csv are provided, companies is used."""
    company = Company(company_id="1", security_id="2", company_name="Test", stock_symbol="TST")
    client = PSEClient(rate_limit_seconds=0.0)

    with patch("pse_data_scraper.downloader.fetch_historical_data", return_value=[]):
        # Should not raise even if input_csv doesn't exist — companies takes precedence
        download_historical_data(
            client=client,
            companies=[company],
            input_csv="/nonexistent/path.csv",
            output_dir=str(tmp_path / "out"),
            cache_dir=None,
        )
