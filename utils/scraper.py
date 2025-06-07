"""
Scrapes company data from the PSE Edge website and saves it to a CSV file.
"""

import requests
from bs4 import BeautifulSoup
import csv
import re
import time

BASE_URL = "https://edge.pse.com.ph/companyDirectory/search.ax?pageNo={}"
OUTPUT_FILE = "finalstocks.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://edge.pse.com.ph/companyDirectory/form.do"
}


def extract_rows_from_page(page_html):
    """
    Extracts company and stock data rows from a page's HTML content.
    """
    soup = BeautifulSoup(page_html, "html.parser")
    rows = soup.select("table.list tbody tr")
    extracted = []

    for row in rows:
        tds = row.find_all("td")
        if len(tds) < 2:
            continue

        name_a = tds[0].find("a")
        symbol_a = tds[1].find("a")

        if not name_a or not symbol_a:
            continue

        match = re.search(r"cmDetail\('(\d+)',\s*'(\d+)'\)", name_a.get("onclick", ""))
        if not match:
            continue

        company_id, security_id = match.groups()
        company_name = name_a.text.strip()
        stock_symbol = symbol_a.text.strip()

        extracted.append((company_id, security_id, company_name, stock_symbol))

    return extracted


def run_scraper():
    """
    Runs the scraper to fetch all pages and save data to a CSV file.
    """
    all_stocks = []
    page = 1

    while True:
        print(f"Fetching page {page}...")
        response = requests.get(BASE_URL.format(page), headers=HEADERS)
        if response.status_code != 200:
            print(f"Failed to fetch page {page}")
            break

        new_rows = extract_rows_from_page(response.text)
        if not new_rows:
            print("No more data. Scraping complete.")
            break

        all_stocks.extend(new_rows)
        page += 1
        time.sleep(1)

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["companyId", "securityId", "companyName", "stockSymbol"])
        writer.writerows(all_stocks)

    print(f"{len(all_stocks)} companies saved to {OUTPUT_FILE}")