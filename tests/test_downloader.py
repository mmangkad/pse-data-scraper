import csv
import json
import logging
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from pse_data_scraper.client import PSEClient
from pse_data_scraper.downloader import (
    CorruptHistoryError,
    download_historical_data,
    fetch_historical_data,
    merge_history_rows,
    read_company_history_csv,
    read_last_csv_date,
    write_company_history_csv,
)
from pse_data_scraper.models import Company, HistoricalPrice

FIXTURES_DIR = Path(__file__).parent / "fixtures"


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


def test_fetch_historical_data_ignores_cache_dir_with_deprecation_notice(
    tmp_path: Path, make_company, mock_client, caplog, monkeypatch
):
    monkeypatch.setattr("pse_data_scraper.utils._cache_deprecation_logged", False)
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

    with caplog.at_level(logging.WARNING):
        first = fetch_historical_data(client, company, "01-01-2024", "01-31-2024", cache_dir=cache_dir)
        second = fetch_historical_data(client, company, "01-01-2024", "01-31-2024", cache_dir=cache_dir)

    assert len(first) == 1
    assert second == first
    assert list(cache_dir.glob("*.json")) == []
    assert caplog.text.count("no longer used") == 1


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


def test_fetch_historical_data_dedupes_repeated_dates(make_company, mock_client):
    # The API sometimes returns the same date more than once (live-verified
    # on BDO's full history); the last record wins.
    data = {
        "chartData": [
            {"CHART_DATE": "Jan 02, 2024 00:00:00", "VALUE": 100.0, "OPEN": 10.0, "CLOSE": 11.0, "HIGH": 12.0, "LOW": 9.0},
            {"CHART_DATE": "Jan 02, 2024 00:00:00", "VALUE": 100.0, "OPEN": 10.0, "CLOSE": 11.0, "HIGH": 12.0, "LOW": 9.0},
            {"CHART_DATE": "Jan 02, 2024 00:00:00", "VALUE": 100.0, "OPEN": 10.0, "CLOSE": 12.0, "HIGH": 12.0, "LOW": 9.0},
            {"CHART_DATE": "Jan 03, 2024 00:00:00", "VALUE": 100.0, "OPEN": 10.0, "CLOSE": 11.0, "HIGH": 12.0, "LOW": 9.0},
        ]
    }
    client = mock_client(data)
    results = fetch_historical_data(client, make_company(), "01-01-2024", "01-31-2024")

    assert [row.date for row in results] == [date(2024, 1, 2), date(2024, 1, 3)]
    assert results[0].close == Decimal("12")


def test_fetch_historical_data_parses_captured_mer_response(make_company, mock_client):
    """Contract test against a real DisclosureCht.ax response captured 2026-09-15."""
    payload = json.loads((FIXTURES_DIR / "disclosure_chart_mer.json").read_text(encoding="utf-8"))
    client = mock_client(payload)
    company = make_company()

    results = fetch_historical_data(client, company, "08-01-2026", "08-31-2026")

    assert len(results) == 19
    assert results[0].date == date(2026, 8, 3)
    assert results[-1].date == date(2026, 8, 28)
    assert results == sorted(results, key=lambda row: row.date)
    assert results[0].symbol == "TST"
    assert results[0].open == Decimal("474.0")
    assert results[0].close == Decimal("487.0")
    assert results[0].low == Decimal("451.2")
    assert results[0].value == Decimal("413592336.0")


def _client_returning(payload: dict) -> PSEClient:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = 200
    resp.json.return_value = payload
    client = PSEClient(rate_limit_seconds=0.0)
    client.post = MagicMock(return_value=resp)
    return client


def _chart_payload(*days: date) -> dict:
    return {
        "chartData": [
            {
                "CHART_DATE": day.strftime("%b %d, %Y 00:00:00"),
                "VALUE": 100.0,
                "OPEN": 10.0,
                "CLOSE": 11.0,
                "HIGH": 12.0,
                "LOW": 9.0,
            }
            for day in days
        ]
    }


def _history_path(tmp_path: Path) -> Path:
    return tmp_path / "TST_Test_Corp.csv"


def _write_history_csv(path: Path, *date_values: str) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Symbol", "Company", "Date", "Value", "Open", "Close", "High", "Low"])
        for value in date_values:
            writer.writerow(["TST", "Test Corp", value, "100", "10", "11", "12", "9"])


def _price(day: date, close: str = "11") -> HistoricalPrice:
    return HistoricalPrice(
        date=day,
        symbol="TST",
        value=Decimal("100"),
        open=Decimal("10"),
        close=Decimal(close),
        high=Decimal("12"),
        low=Decimal("9"),
    )


def test_read_last_csv_date_returns_max_date(tmp_path):
    path = _history_path(tmp_path)
    _write_history_csv(path, "2024-01-02", "2024-01-05", "2024-01-03")
    assert read_last_csv_date(path) == date(2024, 1, 5)


def test_read_last_csv_date_empty_file_returns_none(tmp_path):
    path = _history_path(tmp_path)
    _write_history_csv(path)
    assert read_last_csv_date(path) is None


def test_read_last_csv_date_missing_file_returns_none(tmp_path):
    assert read_last_csv_date(tmp_path / "missing.csv") is None


def test_read_last_csv_date_garbage_dates_return_none(tmp_path):
    path = _history_path(tmp_path)
    _write_history_csv(path, "not-a-date", "also not a date")
    assert read_last_csv_date(path) is None


def test_read_last_csv_date_uses_latest_valid_date(tmp_path):
    path = _history_path(tmp_path)
    _write_history_csv(path, "2024-01-02", "garbage")
    assert read_last_csv_date(path) == date(2024, 1, 2)


def test_read_company_history_csv_round_trips_written_rows(tmp_path, make_company):
    path = _history_path(tmp_path)
    rows = [_price(date(2024, 1, 2)), _price(date(2024, 1, 3), close="12")]
    write_company_history_csv(path, make_company(), rows)

    assert read_company_history_csv(path) == rows


def test_read_company_history_csv_raises_on_malformed_rows(tmp_path):
    path = _history_path(tmp_path)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Symbol", "Company", "Date", "Value", "Open", "Close", "High", "Low"])
        writer.writerow(["TST", "Test Corp", "2024-01-02", "100", "10", "11", "12", "9"])
        writer.writerow(["TST", "Test Corp", "not-a-date", "100", "10", "11", "12", "9"])

    with pytest.raises(CorruptHistoryError, match="malformed row"):
        read_company_history_csv(path)


def test_merge_history_rows_dedupes_with_newer_fetch_winning():
    existing = [_price(date(2024, 1, 2)), _price(date(2024, 1, 5), close="11")]
    fetched = [_price(date(2024, 1, 5), close="99"), _price(date(2024, 1, 8))]

    merged = merge_history_rows(existing, fetched)

    assert [row.date for row in merged] == [date(2024, 1, 2), date(2024, 1, 5), date(2024, 1, 8)]
    assert merged[1].close == Decimal("99")


def test_write_company_history_csv_leaves_no_temp_file(tmp_path, make_company):
    path = _history_path(tmp_path)

    write_company_history_csv(path, make_company(), [_price(date(2024, 1, 2))])

    assert path.exists()
    assert list(tmp_path.glob("*.tmp")) == []


def test_write_company_history_csv_failure_keeps_existing_file(tmp_path, make_company):
    path = _history_path(tmp_path)
    write_company_history_csv(path, make_company(), [_price(date(2024, 1, 2))])
    before = path.read_text(encoding="utf-8")

    def exploding_rows():
        yield _price(date(2024, 1, 3))
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        write_company_history_csv(path, make_company(), exploding_rows())

    assert path.read_text(encoding="utf-8") == before
    assert list(tmp_path.glob("*.tmp")) == []


def test_download_historical_data_full_fetch_when_no_file(tmp_path, make_company):
    client = _client_returning(_chart_payload(date(2024, 1, 2), date(2024, 1, 3)))

    paths = download_historical_data(
        client, companies=[make_company()], output_dir=str(tmp_path), end_date="2024-01-31", cache_dir=None
    )

    assert paths == [_history_path(tmp_path)]
    payload = client.post.call_args.kwargs["json"]
    assert payload["startDate"] == "01-01-1900"
    assert payload["endDate"] == "01-31-2024"
    _, data = _read_csv(_history_path(tmp_path))
    assert len(data) == 2


def test_download_historical_data_incremental_window_is_last_plus_one(tmp_path, make_company):
    _write_history_csv(_history_path(tmp_path), "2024-01-02", "2024-01-05")
    client = _client_returning(_chart_payload(date(2024, 1, 8)))

    download_historical_data(
        client, companies=[make_company()], output_dir=str(tmp_path), end_date="2024-01-31", cache_dir=None
    )

    payload = client.post.call_args.kwargs["json"]
    assert payload["startDate"] == "01-06-2024"
    assert payload["endDate"] == "01-31-2024"


def test_download_historical_data_merges_without_duplicates(tmp_path, make_company):
    path = _history_path(tmp_path)
    _write_history_csv(path, "2024-01-02", "2024-01-05")
    client = _client_returning(_chart_payload(date(2024, 1, 5), date(2024, 1, 8)))

    paths = download_historical_data(
        client, companies=[make_company()], output_dir=str(tmp_path), end_date="2024-01-31", cache_dir=None
    )

    _, data = _read_csv(path)
    assert [row[2] for row in data] == ["2024-01-02", "2024-01-05", "2024-01-08"]
    assert paths == [path]


def test_download_historical_data_no_new_rows_leaves_file_untouched(tmp_path, make_company):
    path = _history_path(tmp_path)
    _write_history_csv(path, "2024-01-02", "2024-01-05")
    before = path.read_bytes()
    client = _client_returning({"chartData": []})

    paths = download_historical_data(
        client, companies=[make_company()], output_dir=str(tmp_path), end_date="2024-01-31", cache_dir=None
    )

    assert paths == [path]
    assert path.read_bytes() == before


def test_download_historical_data_corrupt_file_triggers_full_fetch(tmp_path, make_company):
    path = _history_path(tmp_path)
    _write_history_csv(path, "garbage-date")
    client = _client_returning(_chart_payload(date(2024, 1, 2)))

    download_historical_data(
        client, companies=[make_company()], output_dir=str(tmp_path), end_date="2024-01-31", cache_dir=None
    )

    payload = client.post.call_args.kwargs["json"]
    assert payload["startDate"] == "01-01-1900"
    _, data = _read_csv(path)
    assert [row[2] for row in data] == ["2024-01-02"]


def test_download_historical_data_partially_corrupt_file_triggers_full_fetch(tmp_path, make_company):
    """A file with valid dates but some malformed rows must not lose rows on merge."""
    path = _history_path(tmp_path)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Symbol", "Company", "Date", "Value", "Open", "Close", "High", "Low"])
        writer.writerow(["TST", "Test Corp", "2024-01-02", "100", "10", "11", "12", "9"])
        writer.writerow(["TST", "Test Corp", "2024-01-05", "oops", "10", "11", "12", "9"])
    client = _client_returning(_chart_payload(date(2024, 1, 2), date(2024, 1, 8)))

    download_historical_data(
        client, companies=[make_company()], output_dir=str(tmp_path), end_date="2024-01-31", cache_dir=None
    )

    payload = client.post.call_args.kwargs["json"]
    assert payload["startDate"] == "01-01-1900"
    _, data = _read_csv(path)
    assert [row[2] for row in data] == ["2024-01-02", "2024-01-08"]


def test_download_historical_data_explicit_start_merges_range(tmp_path, make_company):
    path = _history_path(tmp_path)
    _write_history_csv(path, "2024-01-02", "2024-01-05")
    client = _client_returning(_chart_payload(date(2024, 1, 3), date(2024, 1, 8)))

    download_historical_data(
        client,
        companies=[make_company()],
        output_dir=str(tmp_path),
        start_date="2024-01-03",
        end_date="2024-01-31",
        cache_dir=None,
    )

    payload = client.post.call_args.kwargs["json"]
    assert payload["startDate"] == "01-03-2024"
    _, data = _read_csv(path)
    assert [row[2] for row in data] == ["2024-01-02", "2024-01-03", "2024-01-05", "2024-01-08"]


def test_download_historical_data_refresh_ignores_existing_file(tmp_path, make_company):
    path = _history_path(tmp_path)
    _write_history_csv(path, "2024-01-02", "2024-01-05")
    client = _client_returning(_chart_payload(date(2024, 1, 8)))

    download_historical_data(
        client,
        companies=[make_company()],
        output_dir=str(tmp_path),
        end_date="2024-01-31",
        cache_dir=None,
        refresh=True,
    )

    payload = client.post.call_args.kwargs["json"]
    assert payload["startDate"] == "01-01-1900"
    _, data = _read_csv(path)
    assert [row[2] for row in data] == ["2024-01-08"]


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
