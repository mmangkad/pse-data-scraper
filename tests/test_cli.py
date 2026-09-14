import csv
import json
import logging
import sys
from datetime import date
from unittest.mock import patch

import pytest

from pse_data_scraper.cli import main
from pse_data_scraper.models import Company
from pse_data_scraper.scraper import ScrapeIncompleteError, save_companies_to_csv


def _run_main(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["pse", *argv])
    main()


def test_incomplete_scrape_exits_nonzero_with_message(monkeypatch, tmp_path, caplog):
    monkeypatch.chdir(tmp_path)

    with patch(
        "pse_data_scraper.cli.ensure_companies_csv",
        side_effect=ScrapeIncompleteError("directory request for page 2 failed"),
    ):
        with pytest.raises(SystemExit) as excinfo:
            _run_main(monkeypatch, ["companies", "--refresh"])

    assert excinfo.value.code == 1
    assert "directory request for page 2 failed" in caplog.text


def test_unknown_symbols_exit_nonzero_with_message(monkeypatch, tmp_path, caplog):
    monkeypatch.chdir(tmp_path)
    save_companies_to_csv(
        [Company(company_id="1", security_id="2", company_name="Test Corp", stock_symbol="TST")],
        str(tmp_path / "data" / "companies.csv"),
    )

    # The error is raised before any request is made, so no mocking is needed.
    with pytest.raises(SystemExit) as excinfo:
        _run_main(monkeypatch, ["prices", "--symbols", "MERB"])

    assert excinfo.value.code == 1
    assert "None of the requested symbols (MERB)" in caplog.text


def test_companies_refresh_scrapes_and_lists(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    companies = [
        Company(
            company_id="55",
            security_id="347",
            company_name="Asia Amalgamated Holdings Corporation",
            stock_symbol="AAA",
            sector="Holding Firms",
            subsector="Holding Firms",
            listing_date=date(1973, 3, 22),
        ),
        Company(
            company_id="114",
            security_id="123",
            company_name="ABS-CBN Corporation",
            stock_symbol="ABS",
            sector="Services",
            subsector="Media",
        ),
    ]

    with patch("pse_data_scraper.pipeline.scrape_companies", return_value=companies):
        _run_main(monkeypatch, ["companies", "--refresh", "--list"])

    out = capsys.readouterr().out
    assert "AAA\tAsia Amalgamated Holdings Corporation" in out
    assert "ABS\tABS-CBN Corporation" in out
    companies_csv = tmp_path / "data" / "companies.csv"
    content = companies_csv.read_text(encoding="utf-8")
    assert "sector,subsector,listingDate" in content
    assert "Holding Firms,Holding Firms,1973-03-22" in content


def test_cache_flags_log_deprecation_notice(monkeypatch, tmp_path, caplog):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("pse_data_scraper.utils._cache_deprecation_logged", False)
    save_companies_to_csv(
        [Company(company_id="1", security_id="2", company_name="Test Corp", stock_symbol="TST")],
        str(tmp_path / "data" / "companies.csv"),
    )

    with patch("pse_data_scraper.cli.download_historical_data"):
        with caplog.at_level(logging.WARNING):
            _run_main(monkeypatch, ["prices", "--cache-dir", str(tmp_path / "c"), "--no-cache"])

    assert caplog.text.count("no longer used") == 1


def test_prices_refresh_redownloads_prices_without_rescraping_companies(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    save_companies_to_csv(
        [Company(company_id="1", security_id="2", company_name="Test Corp", stock_symbol="TST")],
        str(tmp_path / "data" / "companies.csv"),
    )

    with patch("pse_data_scraper.cli.download_historical_data") as download:
        _run_main(monkeypatch, ["prices", "--refresh"])

    download.assert_called_once()
    assert download.call_args.kwargs["refresh"] is True
    # The company list came from the existing CSV, not a re-scrape.
    assert [company.stock_symbol for company in download.call_args.kwargs["companies"]] == ["TST"]


def test_sync_refresh_refreshes_companies_and_prices(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    with patch("pse_data_scraper.pipeline.ensure_companies_csv") as ensure, patch(
        "pse_data_scraper.pipeline.download_prices"
    ) as download, patch("pse_data_scraper.pipeline.export_prices"):
        _run_main(monkeypatch, ["sync", "--refresh"])

    assert ensure.call_args.kwargs["refresh"] is True
    assert download.call_args.kwargs["refresh"] is True


def test_sector_and_keyword_flags_reach_company_scrape(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    with patch("pse_data_scraper.cli.ensure_companies_csv") as ensure:
        _run_main(
            monkeypatch,
            ["companies", "--sector", "Mining and Oil", "--keyword", "Ayala"],
        )

    assert ensure.call_args.kwargs["sector"] == "Mining and Oil"
    assert ensure.call_args.kwargs["keyword"] == "Ayala"


def test_timeout_flag_reaches_client(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    with patch("pse_data_scraper.cli.PSEClient") as client_cls, patch(
        "pse_data_scraper.cli.ensure_companies_csv"
    ):
        _run_main(monkeypatch, ["companies", "--timeout", "5"])

    assert client_cls.call_args.kwargs["timeout_seconds"] == 5


def test_timeout_from_config_reaches_client(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pse.toml").write_text("[network]\ntimeout = 12\n", encoding="utf-8")

    with patch("pse_data_scraper.cli.PSEClient") as client_cls, patch(
        "pse_data_scraper.cli.ensure_companies_csv"
    ):
        _run_main(monkeypatch, ["companies"])

    assert client_cls.call_args.kwargs["timeout_seconds"] == 12


def test_prices_sector_filters_existing_company_list(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    save_companies_to_csv(
        [
            Company(
                company_id="1",
                security_id="2",
                company_name="Ayala Corporation",
                stock_symbol="AC",
                sector="Holding Firms",
            ),
            Company(
                company_id="3",
                security_id="4",
                company_name="BDO Unibank, Inc.",
                stock_symbol="BDO",
                sector="Financials",
            ),
        ],
        str(tmp_path / "data" / "companies.csv"),
    )

    with patch("pse_data_scraper.cli.download_historical_data") as download:
        _run_main(monkeypatch, ["prices", "--sector", "Financials"])

    downloaded = download.call_args.kwargs["companies"]
    assert [company.stock_symbol for company in downloaded] == ["BDO"]


def test_sector_and_keyword_from_config_reach_company_scrape(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pse.toml").write_text(
        '[download]\nsector = "Services"\nkeyword = "Ayala"\n', encoding="utf-8"
    )

    with patch("pse_data_scraper.cli.ensure_companies_csv") as ensure:
        _run_main(monkeypatch, ["companies"])

    assert ensure.call_args.kwargs["sector"] == "Services"
    assert ensure.call_args.kwargs["keyword"] == "Ayala"


def _write_dataset(tmp_path) -> None:
    """A minimal local dataset: companies.csv + combined.csv with two dates."""
    save_companies_to_csv(
        [Company(company_id="1", security_id="2", company_name="Test Corp", stock_symbol="TST")],
        str(tmp_path / "data" / "companies.csv"),
    )
    with (tmp_path / "data" / "combined.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Symbol", "Company", "Date", "Value", "Open", "Close", "High", "Low"])
        writer.writerow(["TST", "Test Corp", "2024-01-02", "100", "10", "11", "12", "9"])
        writer.writerow(["TST", "Test Corp", "2024-01-05", "100", "10", "11", "12", "9"])


def test_status_shows_freshness_line(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    _write_dataset(tmp_path)

    _run_main(monkeypatch, ["status"])

    out = capsys.readouterr().out
    assert "Latest price date: 2024-01-05 (EDGE data lags ~1 trading day)" in out


def test_status_json_output(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    _write_dataset(tmp_path)

    _run_main(monkeypatch, ["status", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert set(payload) == {"companies", "history", "combined"}
    assert payload["companies"]["rows"] == 1
    assert payload["combined"]["rows"] == 2
    assert payload["combined"]["date_range"] == ["2024-01-02", "2024-01-05"]
