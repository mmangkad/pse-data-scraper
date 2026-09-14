"""
Scrape company listings from PSE EDGE.
"""

from __future__ import annotations

import csv
import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, List, NamedTuple, Optional, Set, Tuple

from bs4 import BeautifulSoup

from pse_data_scraper.client import PSEClient
from pse_data_scraper.models import Company
from pse_data_scraper.utils import OUTPUT_DATE_FORMAT, format_output_date

logger = logging.getLogger(__name__)

COMPANY_DIRECTORY_URL = "https://edge.pse.com.ph/companyDirectory/search.ax?pageNo={page}"
COMPANY_DIRECTORY_REFERER = "https://edge.pse.com.ph/companyDirectory/form.do"

LISTING_DATE_FORMAT = "%b %d, %Y"

COMPANIES_CSV_HEADER = [
    "companyId",
    "securityId",
    "companyName",
    "stockSymbol",
    "sector",
    "subsector",
    "listingDate",
]

# Count span: "<span class="count"> [1 / 6] [Total 282] </span>" — current page / total pages / total rows.
COUNT_SPAN_PATTERN = re.compile(r"\[\s*(\d+)\s*/\s*(\d+)\s*\]\s*\[\s*Total\s+(\d+)\s*\]")
# Paging controls reference the absolute last page via goPage(N).
GO_PAGE_PATTERN = re.compile(r"goPage\((\d+)\)")


class ScrapeIncompleteError(RuntimeError):
    """Raised when a company directory scrape cannot be trusted to be complete."""


class PageMeta(NamedTuple):
    """Pagination markers extracted from a directory search response."""

    current_page: Optional[int]
    total_pages: Optional[int]
    total_rows: Optional[int]


def _cell_text(tds: List, index: int) -> str:
    if len(tds) <= index:
        return ""
    return tds[index].text.strip()


def _parse_listing_date(text: str) -> Optional[date]:
    """Parse a directory listing date like 'Mar 22, 1973' (None if absent/unparseable)."""
    if not text:
        return None
    try:
        return datetime.strptime(text, LISTING_DATE_FORMAT).date()
    except ValueError:
        logger.warning("Ignoring unparseable listing date: %r", text)
        return None


def _parse_csv_listing_date(text: Optional[str]) -> Optional[date]:
    """Parse an ISO listing date from companies.csv (None if absent/unparseable)."""
    if not text:
        return None
    try:
        return datetime.strptime(text, OUTPUT_DATE_FORMAT).date()
    except ValueError:
        logger.warning("Ignoring unparseable listingDate in companies CSV: %r", text)
        return None


def parse_page_meta(page_html: str) -> Optional[PageMeta]:
    """Extract pagination markers from a directory search response.

    Primary source is the count span (e.g. ``[1 / 6] [Total 282]``); if absent,
    fall back to the largest ``goPage(N)`` reference, which points at the
    absolute last page. Returns None when neither marker is present.
    """
    match = COUNT_SPAN_PATTERN.search(page_html)
    if match:
        return PageMeta(
            current_page=int(match.group(1)),
            total_pages=int(match.group(2)),
            total_rows=int(match.group(3)),
        )
    last_page = max(
        (int(found.group(1)) for found in GO_PAGE_PATTERN.finditer(page_html)),
        default=None,
    )
    if last_page is not None:
        return PageMeta(current_page=None, total_pages=last_page, total_rows=None)
    return None


def parse_companies_from_html(page_html: str) -> List[Company]:
    soup = BeautifulSoup(page_html, "html.parser")
    rows = soup.select("table.list tbody tr")
    extracted: List[Company] = []

    for row in rows:
        tds = row.find_all("td")
        if len(tds) < 2:
            continue

        name_anchor = tds[0].find("a")
        symbol_anchor = tds[1].find("a")
        if not name_anchor or not symbol_anchor:
            continue

        onclick_value = name_anchor.get("onclick", "")
        match = re.search(r"cmDetail\('(\d+)',\s*'(\d+)'\)", onclick_value)
        if not match:
            continue

        company_id, security_id = match.groups()
        extracted.append(
            Company(
                company_id=company_id,
                security_id=security_id,
                company_name=name_anchor.text.strip(),
                stock_symbol=symbol_anchor.text.strip(),
                sector=_cell_text(tds, 2),
                subsector=_cell_text(tds, 3),
                listing_date=_parse_listing_date(_cell_text(tds, 4)),
            )
        )

    return extracted


def scrape_companies(
    client: PSEClient,
    max_pages: Optional[int] = None,
) -> List[Company]:
    all_companies: List[Company] = []
    seen_keys: Set[Tuple[str, str]] = set()
    duplicates = 0
    page = 1
    total_pages: Optional[int] = None
    total_rows: Optional[int] = None
    hit_page_limit = False

    while True:
        if max_pages is not None and page > max_pages:
            hit_page_limit = True
            break

        url = COMPANY_DIRECTORY_URL.format(page=page)
        logger.info("Fetching page %s", page)
        response = client.get(url, headers={"Referer": COMPANY_DIRECTORY_REFERER})
        if response.status_code != 200:
            raise ScrapeIncompleteError(
                f"Company directory request for page {page} failed "
                f"(status {response.status_code}); collected {len(all_companies)} companies so far."
            )

        meta = parse_page_meta(response.text)
        if meta is not None:
            if meta.total_pages is not None:
                total_pages = meta.total_pages
            if meta.total_rows is not None:
                total_rows = meta.total_rows

        new_rows = parse_companies_from_html(response.text)
        if not new_rows:
            logger.info("No more data. Scraping complete.")
            break

        for company in new_rows:
            key = (company.company_id, company.security_id)
            if key in seen_keys:
                duplicates += 1
                continue
            seen_keys.add(key)
            all_companies.append(company)
        page += 1

    if duplicates:
        logger.warning("Skipped %s duplicate rows in company directory", duplicates)

    # A page-limited run is deliberately truncated, so completeness cannot be
    # verified; the pipeline guards such results before overwriting anything.
    if not hit_page_limit:
        if total_pages is not None and page - 1 != total_pages:
            raise ScrapeIncompleteError(
                f"Company directory pagination mismatch: stopped after page {page - 1} "
                f"but the directory reports {total_pages} pages "
                f"({len(all_companies)} companies collected)."
            )
        if total_rows is not None and len(all_companies) < total_rows:
            raise ScrapeIncompleteError(
                f"Company directory row count mismatch: collected {len(all_companies)} "
                f"companies but the directory reports {total_rows}."
            )

    return all_companies


def save_companies_to_csv(companies: Iterable[Company], output_file: str) -> None:
    company_list = list(companies)
    output_path = Path(output_file)
    if output_path.parent and not output_path.parent.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(COMPANIES_CSV_HEADER)
        for company in company_list:
            writer.writerow(
                [
                    company.company_id,
                    company.security_id,
                    company.company_name,
                    company.stock_symbol,
                    company.sector,
                    company.subsector,
                    format_output_date(company.listing_date) if company.listing_date is not None else "",
                ]
            )

    logger.info("Saved %s companies to %s", len(company_list), output_file)


def load_companies_from_csv(input_csv: str) -> List[Company]:
    companies: List[Company] = []
    with open(input_csv, encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            companies.append(
                Company(
                    company_id=row["companyId"],
                    security_id=row["securityId"],
                    company_name=row["companyName"],
                    stock_symbol=row["stockSymbol"],
                    sector=row.get("sector") or "",
                    subsector=row.get("subsector") or "",
                    listing_date=_parse_csv_listing_date(row.get("listingDate")),
                )
            )
    return companies
