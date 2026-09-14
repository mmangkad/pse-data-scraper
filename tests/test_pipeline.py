from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from pse_data_scraper.client import PSEClient
from pse_data_scraper.models import Company
from pse_data_scraper.pipeline import ensure_companies_csv
from pse_data_scraper.scraper import ScrapeIncompleteError, save_companies_to_csv


def _make_company(symbol: str = "TST", company_id: str = "1") -> Company:
    return Company(
        company_id=company_id,
        security_id="2",
        company_name=f"Company {symbol}",
        stock_symbol=symbol,
    )


def _write_companies_csv(path, companies) -> None:
    save_companies_to_csv(companies, str(path))


def test_ensure_companies_csv_uses_existing_without_refresh(tmp_path):
    companies_csv = tmp_path / "companies.csv"
    _write_companies_csv(companies_csv, [_make_company("AAA"), _make_company("BDO")])

    client = PSEClient(rate_limit_seconds=0.0)
    client.get = MagicMock()

    result = ensure_companies_csv(client, str(companies_csv))

    assert [company.stock_symbol for company in result] == ["AAA", "BDO"]
    client.get.assert_not_called()


def test_ensure_companies_csv_scrapes_and_saves_when_missing(tmp_path):
    companies_csv = tmp_path / "companies.csv"
    companies = [
        _make_company("AAA", company_id="1"),
        _make_company("BDO", company_id="2"),
    ]
    client = PSEClient(rate_limit_seconds=0.0)

    with patch("pse_data_scraper.pipeline.scrape_companies", return_value=companies) as mock_scrape:
        result = ensure_companies_csv(client, str(companies_csv))

    mock_scrape.assert_called_once_with(client, max_pages=None, keyword=None, sector=None)
    assert result == companies
    assert companies_csv.exists()
    content = companies_csv.read_text(encoding="utf-8")
    assert "sector,subsector,listingDate" in content


def test_ensure_companies_csv_passes_directory_filters(tmp_path):
    companies_csv = tmp_path / "companies.csv"
    client = PSEClient(rate_limit_seconds=0.0)

    with patch("pse_data_scraper.pipeline.scrape_companies", return_value=[]) as mock_scrape:
        ensure_companies_csv(client, str(companies_csv), keyword="Ayala", sector="Services")

    mock_scrape.assert_called_once_with(client, max_pages=None, keyword="Ayala", sector="Services")


def test_ensure_companies_csv_keeps_existing_file_on_incomplete_scrape(tmp_path):
    companies_csv = tmp_path / "companies.csv"
    _write_companies_csv(companies_csv, [_make_company(f"C{i}") for i in range(3)])
    before = companies_csv.read_text(encoding="utf-8")

    client = PSEClient(rate_limit_seconds=0.0)
    with patch(
        "pse_data_scraper.pipeline.scrape_companies",
        side_effect=ScrapeIncompleteError("directory request for page 2 failed"),
    ):
        with pytest.raises(ScrapeIncompleteError, match="Kept the existing company list"):
            ensure_companies_csv(client, str(companies_csv), refresh=True)

    assert companies_csv.read_text(encoding="utf-8") == before


def test_ensure_companies_csv_incomplete_first_scrape_writes_nothing(tmp_path):
    companies_csv = tmp_path / "companies.csv"
    client = PSEClient(rate_limit_seconds=0.0)

    with patch(
        "pse_data_scraper.pipeline.scrape_companies",
        side_effect=ScrapeIncompleteError("pagination mismatch"),
    ):
        with pytest.raises(ScrapeIncompleteError, match="pagination mismatch"):
            ensure_companies_csv(client, str(companies_csv))

    assert not companies_csv.exists()


def test_ensure_companies_csv_refuses_smaller_page_limited_scrape(tmp_path):
    companies_csv = tmp_path / "companies.csv"
    _write_companies_csv(companies_csv, [_make_company(f"C{i}") for i in range(3)])
    before = companies_csv.read_text(encoding="utf-8")

    client = PSEClient(rate_limit_seconds=0.0)
    with patch(
        "pse_data_scraper.pipeline.scrape_companies",
        return_value=[_make_company("AAA"), _make_company("BDO")],
    ) as mock_scrape:
        with pytest.raises(ScrapeIncompleteError, match="Refusing to overwrite"):
            ensure_companies_csv(client, str(companies_csv), refresh=True, max_pages=1)

    mock_scrape.assert_called_once_with(client, max_pages=1, keyword=None, sector=None)
    assert companies_csv.read_text(encoding="utf-8") == before


def test_ensure_companies_csv_allows_smaller_complete_scrape(tmp_path):
    # A complete scrape may legitimately find fewer companies than an old file
    # (e.g. delistings), so a full refresh must be allowed to shrink the list.
    companies_csv = tmp_path / "companies.csv"
    _write_companies_csv(companies_csv, [_make_company("AAA"), _make_company("BDO")])

    client = PSEClient(rate_limit_seconds=0.0)
    with patch("pse_data_scraper.pipeline.scrape_companies", return_value=[_make_company("AAA")]):
        result = ensure_companies_csv(client, str(companies_csv), refresh=True)

    assert [company.stock_symbol for company in result] == ["AAA"]


def test_ensure_companies_csv_allows_page_limited_scrape_that_grows(tmp_path):
    companies_csv = tmp_path / "companies.csv"
    _write_companies_csv(companies_csv, [_make_company("AAA")])

    client = PSEClient(rate_limit_seconds=0.0)
    with patch(
        "pse_data_scraper.pipeline.scrape_companies",
        return_value=[_make_company("AAA"), _make_company("BDO")],
    ):
        result = ensure_companies_csv(client, str(companies_csv), refresh=True, max_pages=1)

    assert [company.stock_symbol for company in result] == ["AAA", "BDO"]
