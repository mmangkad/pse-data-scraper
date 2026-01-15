"""
HTTP client with retry and rate-limiting for PSE EDGE endpoints.
"""

from __future__ import annotations

import time
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/html, */*; q=0.01",
    "Connection": "keep-alive",
}


class PSEClient:
    """
    Simple HTTP client that enforces a minimum delay between requests
    and retries transient failures.
    """

    def __init__(
        self,
        rate_limit_seconds: float = 0.6,
        timeout_seconds: int = 30,
        session: Optional[requests.Session] = None,
        max_retries: int = 4,
        backoff_factor: float = 0.5,
    ) -> None:
        self.rate_limit_seconds = max(rate_limit_seconds, 0.0)
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()
        self._last_request_at: Optional[float] = None
        self._configure_retries(max_retries=max_retries, backoff_factor=backoff_factor)
        self.session.headers.update(DEFAULT_HEADERS)

    def _configure_retries(self, max_retries: int, backoff_factor: float) -> None:
        retry = Retry(
            total=max_retries,
            read=max_retries,
            connect=max_retries,
            status=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "POST"),
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _respect_rate_limit(self) -> None:
        if self.rate_limit_seconds <= 0:
            return
        now = time.monotonic()
        if self._last_request_at is None:
            self._last_request_at = now
            return
        elapsed = now - self._last_request_at
        if elapsed < self.rate_limit_seconds:
            time.sleep(self.rate_limit_seconds - elapsed)
        self._last_request_at = time.monotonic()

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        self._respect_rate_limit()
        if "timeout" not in kwargs:
            kwargs["timeout"] = self.timeout_seconds
        return self.session.request(method=method, url=url, **kwargs)

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> requests.Response:
        return self.request("POST", url, **kwargs)
