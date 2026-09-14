import csv
import logging
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from pse_data_scraper.client import PSEClient
from pse_data_scraper.models import Company
from pse_data_scraper.scraper import (
    ScrapeIncompleteError,
    load_companies_from_csv,
    parse_companies_from_html,
    parse_page_meta,
    save_companies_to_csv,
    scrape_companies,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"

SAMPLE_HTML = """
<table class="list">
  <tbody>
    <tr>
      <td><a onclick="cmDetail('123','456')">Acme Corporation</a></td>
      <td><a>ACME</a></td>
    </tr>
  </tbody>
</table>
"""

SAMPLE_HTML_FULL_ROW = """
<table class="list">
  <tbody>
    <tr>
      <td><a onclick="cmDetail('55','347')">Asia Amalgamated Holdings Corporation</a></td>
      <td><a>AAA</a></td>
      <td>Holding Firms</td>
      <td>Holding Firms</td>
      <td>Mar 22, 1973</td>
    </tr>
  </tbody>
</table>
"""


def _row(company_id: str, security_id: str, name: str, symbol: str) -> str:
    return (
        f"<tr><td><a onclick=\"cmDetail('{company_id}','{security_id}')\">{name}</a></td>"
        f"<td><a>{symbol}</a></td></tr>"
    )


def _table(rows_html: str) -> str:
    return f'<table class="list"><tbody>\n{rows_html}\n</tbody></table>'


def _directory_page(rows_html: str, current: int, total_pages: int, total_rows: int) -> str:
    return (
        f'<span class="count"> [{current} / {total_pages}] [Total {total_rows}] </span>\n'
        + _table(rows_html)
    )


def _mock_response(text: str, status_code: int = 200) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.text = text
    return resp


def test_parse_companies_from_html_extracts_rows():
    companies = parse_companies_from_html(SAMPLE_HTML)

    assert len(companies) == 1
    company = companies[0]
    assert company.company_id == "123"
    assert company.security_id == "456"
    assert company.company_name == "Acme Corporation"
    assert company.stock_symbol == "ACME"
    # Rows without metadata columns keep the defaults.
    assert company.sector == ""
    assert company.subsector == ""
    assert company.listing_date is None


def test_parse_companies_from_html_extracts_metadata():
    companies = parse_companies_from_html(SAMPLE_HTML_FULL_ROW)

    assert len(companies) == 1
    company = companies[0]
    assert company.sector == "Holding Firms"
    assert company.subsector == "Holding Firms"
    assert company.listing_date == date(1973, 3, 22)


def test_parse_companies_from_html_keeps_row_with_bad_listing_date():
    html = SAMPLE_HTML_FULL_ROW.replace("<td>Mar 22, 1973</td>", "<td>not a date</td>")
    companies = parse_companies_from_html(html)

    assert len(companies) == 1
    assert companies[0].listing_date is None
    assert companies[0].stock_symbol == "AAA"


def test_parse_companies_from_html_empty_table():
    html = '<table class="list"><tbody></tbody></table>'
    companies = parse_companies_from_html(html)
    assert companies == []


def test_parse_real_directory_page_fixture():
    html = (FIXTURES_DIR / "company_directory_page1.html").read_text(encoding="utf-8")
    companies = parse_companies_from_html(html)

    assert len(companies) == 50
    first = companies[0]
    assert first.company_id == "55"
    assert first.security_id == "347"
    assert first.company_name == "Asia Amalgamated Holdings Corporation"
    assert first.stock_symbol == "AAA"
    assert first.sector == "Holding Firms"
    assert first.subsector == "Holding Firms"
    assert first.listing_date == date(1973, 3, 22)
    assert all(company.sector for company in companies)
    assert all(company.listing_date is not None for company in companies)


def test_parse_page_meta_from_fixture():
    html = (FIXTURES_DIR / "company_directory_page1.html").read_text(encoding="utf-8")

    assert parse_page_meta(html) == (1, 6, 282)


def test_parse_page_meta_tolerates_whitespace():
    html = "<span class=\"count\">\n\n[1 /\n6]\n[Total 282]\n</span>"

    assert parse_page_meta(html) == (1, 6, 282)


def test_parse_page_meta_go_page_fallback():
    html = '<div class="paging"><a onclick="goPage(2)">2</a><a onclick="goPage(6)"><img alt="last page"/></a></div>'

    assert parse_page_meta(html) == (None, 6, None)


def test_parse_page_meta_returns_none_without_markers():
    assert parse_page_meta(SAMPLE_HTML) is None


def test_scrape_companies_paginates():
    client = PSEClient(rate_limit_seconds=0.0)
    responses = [
        _mock_response(_table(_row(str(index), str(index * 10), f"Company {index}", f"C{index}")))
        for index in range(1, 4)
    ]
    # 4th call returns empty page to stop pagination
    responses.append(_mock_response('<table class="list"><tbody></tbody></table>'))

    client.get = MagicMock(side_effect=responses)
    result = scrape_companies(client)

    assert len(result) == 3
    assert client.get.call_count == 4


def test_scrape_companies_raises_on_non200():
    client = PSEClient(rate_limit_seconds=0.0)
    ok_resp = MagicMock(spec=requests.Response)
    ok_resp.status_code = 200
    ok_resp.text = SAMPLE_HTML

    fail_resp = MagicMock(spec=requests.Response)
    fail_resp.status_code = 500
    fail_resp.text = ""

    client.get = MagicMock(side_effect=[ok_resp, fail_resp])

    with pytest.raises(ScrapeIncompleteError, match="page 2 failed"):
        scrape_companies(client)

    assert client.get.call_count == 2


def test_scrape_companies_raises_on_page_count_mismatch():
    client = PSEClient(rate_limit_seconds=0.0)
    page1 = _directory_page(_row("1", "11", "Alpha", "ALP"), current=1, total_pages=6, total_rows=282)
    empty_page = '<table class="list"><tbody></tbody></table>'
    client.get = MagicMock(side_effect=[_mock_response(page1), _mock_response(empty_page)])

    with pytest.raises(ScrapeIncompleteError, match="pagination mismatch"):
        scrape_companies(client)


def test_scrape_companies_raises_on_row_count_mismatch():
    client = PSEClient(rate_limit_seconds=0.0)
    page1 = _directory_page(_row("1", "11", "Alpha", "ALP"), current=1, total_pages=1, total_rows=2)
    empty_page = '<table class="list"><tbody></tbody></table>'
    client.get = MagicMock(side_effect=[_mock_response(page1), _mock_response(empty_page)])

    with pytest.raises(ScrapeIncompleteError, match="row count mismatch"):
        scrape_companies(client)


def test_scrape_companies_accepts_extra_rows():
    # Rows can only be added between requests; more rows than the span's total is fine.
    client = PSEClient(rate_limit_seconds=0.0)
    rows = _row("1", "11", "Alpha", "ALP") + _row("2", "22", "Beta", "BET")
    page1 = _directory_page(rows, current=1, total_pages=1, total_rows=1)
    empty_page = '<table class="list"><tbody></tbody></table>'
    client.get = MagicMock(side_effect=[_mock_response(page1), _mock_response(empty_page)])

    result = scrape_companies(client)

    assert len(result) == 2


def test_scrape_companies_dedupes_rows_across_pages(caplog):
    client = PSEClient(rate_limit_seconds=0.0)
    page1 = _directory_page(
        _row("1", "11", "Alpha", "ALP") + _row("2", "22", "Beta", "BET"),
        current=1,
        total_pages=2,
        total_rows=3,
    )
    page2 = _directory_page(
        _row("2", "22", "Beta", "BET") + _row("3", "33", "Gamma", "GAM"),
        current=2,
        total_pages=2,
        total_rows=3,
    )
    empty_page = '<table class="list"><tbody></tbody></table>'
    client.get = MagicMock(
        side_effect=[_mock_response(page1), _mock_response(page2), _mock_response(empty_page)]
    )

    with caplog.at_level(logging.WARNING):
        result = scrape_companies(client)

    assert [company.stock_symbol for company in result] == ["ALP", "BET", "GAM"]
    assert "1 duplicate" in caplog.text


def test_scrape_companies_max_pages_skips_completeness_checks():
    client = PSEClient(rate_limit_seconds=0.0)
    page1 = _directory_page(_row("1", "11", "Alpha", "ALP"), current=1, total_pages=6, total_rows=282)
    client.get = MagicMock(return_value=_mock_response(page1))

    result = scrape_companies(client, max_pages=1)

    assert len(result) == 1
    assert client.get.call_count == 1


def test_scrape_companies_respects_max_pages():
    client = PSEClient(rate_limit_seconds=0.0)
    responses = [
        _mock_response(_table(_row(str(index), str(index * 10), f"Company {index}", f"C{index}")))
        for index in range(1, 3)
    ]
    client.get = MagicMock(side_effect=responses)

    result = scrape_companies(client, max_pages=2)

    assert len(result) == 2
    assert client.get.call_count == 2


def test_scrape_companies_passes_filters_as_params():
    client = PSEClient(rate_limit_seconds=0.0)
    client.get = MagicMock(return_value=_mock_response('<table class="list"><tbody></tbody></table>'))

    scrape_companies(client, keyword="Aya", sector="Services", subsector="Media")

    assert client.get.call_args.kwargs["params"] == {
        "pageNo": 1,
        "keyword": "Aya",
        "sector": "Services",
        "subsector": "Media",
    }


def test_scrape_companies_omits_unset_filters():
    client = PSEClient(rate_limit_seconds=0.0)
    client.get = MagicMock(return_value=_mock_response('<table class="list"><tbody></tbody></table>'))

    scrape_companies(client)

    assert client.get.call_args.kwargs["params"] == {"pageNo": 1}


def test_save_and_load_companies_csv_round_trip(tmp_path):
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
    output_file = tmp_path / "companies.csv"

    save_companies_to_csv(companies, str(output_file))
    loaded = load_companies_from_csv(str(output_file))

    with output_file.open(newline="", encoding="utf-8") as handle:
        header = next(csv.reader(handle))
    assert header == ["companyId", "securityId", "companyName", "stockSymbol", "sector", "subsector", "listingDate"]
    assert loaded == companies


def test_load_companies_csv_reads_legacy_four_column_files(tmp_path):
    output_file = tmp_path / "companies.csv"
    with output_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["companyId", "securityId", "companyName", "stockSymbol"])
        writer.writerow(["123", "456", "Acme Corporation", "ACME"])

    loaded = load_companies_from_csv(str(output_file))

    assert loaded == [
        Company(
            company_id="123",
            security_id="456",
            company_name="Acme Corporation",
            stock_symbol="ACME",
        )
    ]


def test_load_companies_csv_tolerates_bad_listing_date(tmp_path):
    output_file = tmp_path / "companies.csv"
    with output_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["companyId", "securityId", "companyName", "stockSymbol", "sector", "subsector", "listingDate"])
        writer.writerow(["123", "456", "Acme Corporation", "ACME", "Services", "Media", "not-a-date"])

    loaded = load_companies_from_csv(str(output_file))

    assert len(loaded) == 1
    assert loaded[0].listing_date is None
