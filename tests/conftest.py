from unittest.mock import MagicMock

import pytest
import requests

from pse_data_scraper.client import PSEClient
from pse_data_scraper.models import Company


@pytest.fixture
def make_company():
    def _make_company(symbol: str = "TST", company_id: str = "1", security_id: str = "2", name: str = "Test Corp") -> Company:
        return Company(company_id=company_id, security_id=security_id, company_name=name, stock_symbol=symbol)
    return _make_company


@pytest.fixture
def mock_client():
    def _mock_client(response_json: dict) -> PSEClient:
        resp = MagicMock(spec=requests.Response)
        resp.status_code = 200
        resp.json.return_value = response_json
        resp.raise_for_status = MagicMock()

        client = PSEClient(rate_limit_seconds=0.0)
        client.post = MagicMock(return_value=resp)
        return client
    return _mock_client
