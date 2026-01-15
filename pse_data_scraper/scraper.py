"""
Scrape company listings from PSE EDGE.
"""

from __future__ import annotations

import csv
import logging
import re
from pathlib import Path
from typing import Iterable, List, Optional

from bs4 import BeautifulSoup

from pse_data_scraper.client import PSEClient
from pse_data_scraper.models import Company

logger = logging.getLogger(__name__)

COMPANY_DIRECTORY_URL = "https://edge.pse.com.ph/companyDirectory/search.ax?pageNo={page}"
COMPANY_DIRECTORY_REFERER = "https://edge.pse.com.ph/companyDirectory/form.do"


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
            )
        )

    return extracted


def scrape_companies(
    client: PSEClient,
    max_pages: Optional[int] = None,
) -> List[Company]:
    all_companies: List[Company] = []
    page = 1

    while True:
        if max_pages is not None and page > max_pages:
            break

        url = COMPANY_DIRECTORY_URL.format(page=page)
        logger.info("Fetching page %s", page)
        response = client.get(url, headers={"Referer": COMPANY_DIRECTORY_REFERER})
        if response.status_code != 200:
            logger.warning("Failed to fetch page %s (status %s)", page, response.status_code)
            break

        new_rows = parse_companies_from_html(response.text)
        if not new_rows:
            logger.info("No more data. Scraping complete.")
            break

        all_companies.extend(new_rows)
        page += 1

    return all_companies


def save_companies_to_csv(companies: Iterable[Company], output_file: str) -> None:
    company_list = list(companies)
    output_path = Path(output_file)
    if output_path.parent and not output_path.parent.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["companyId", "securityId", "companyName", "stockSymbol"])
        for company in company_list:
            writer.writerow(
                [company.company_id, company.security_id, company.company_name, company.stock_symbol]
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
                )
            )
    return companies
