from unittest.mock import MagicMock

import requests

from pse_data_scraper.client import PSEClient
from pse_data_scraper.scraper import parse_companies_from_html, scrape_companies


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


def test_parse_companies_from_html_extracts_rows():
    companies = parse_companies_from_html(SAMPLE_HTML)

    assert len(companies) == 1
    company = companies[0]
    assert company.company_id == "123"
    assert company.security_id == "456"
    assert company.company_name == "Acme Corporation"
    assert company.stock_symbol == "ACME"


def test_parse_companies_from_html_empty_table():
    html = '<table class="list"><tbody></tbody></table>'
    companies = parse_companies_from_html(html)
    assert companies == []


def test_scrape_companies_paginates():
    client = PSEClient(rate_limit_seconds=0.0)
    responses = []

    for _ in range(3):
        resp = MagicMock(spec=requests.Response)
        resp.status_code = 200
        resp.text = SAMPLE_HTML
        responses.append(resp)

    # 4th call returns empty page to stop pagination
    empty_resp = MagicMock(spec=requests.Response)
    empty_resp.status_code = 200
    empty_resp.text = '<table class="list"><tbody></tbody></table>'
    responses.append(empty_resp)

    client.get = MagicMock(side_effect=responses)
    result = scrape_companies(client)

    assert len(result) == 3
    assert client.get.call_count == 4


def test_scrape_companies_stops_on_non200():
    client = PSEClient(rate_limit_seconds=0.0)
    ok_resp = MagicMock(spec=requests.Response)
    ok_resp.status_code = 200
    ok_resp.text = SAMPLE_HTML

    fail_resp = MagicMock(spec=requests.Response)
    fail_resp.status_code = 500
    fail_resp.text = ""

    client.get = MagicMock(side_effect=[ok_resp, fail_resp])
    result = scrape_companies(client)

    # Should return partial results (1 page worth), not crash
    assert len(result) == 1
    assert client.get.call_count == 2


def test_scrape_companies_respects_max_pages():
    client = PSEClient(rate_limit_seconds=0.0)
    resp = MagicMock(spec=requests.Response)
    resp.status_code = 200
    resp.text = SAMPLE_HTML
    client.get = MagicMock(return_value=resp)

    result = scrape_companies(client, max_pages=2)

    assert len(result) == 2
    assert client.get.call_count == 2
