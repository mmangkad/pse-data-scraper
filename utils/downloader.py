"""
Downloads historical stock data for companies listed in finalstocks.csv.
"""

import os
import csv
import requests
from datetime import datetime

REQUEST_PATH = 'https://edge.pse.com.ph/common/DisclosureCht.ax'

HEADERS = {
    'Origin': 'https://edge.pse.com.ph',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Accept-Language': 'en-US,en;q=0.5',
    'User-Agent': 'Mozilla/5.0',
    'Content-Type': 'application/json',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Referer': 'https://edge.pse.com.ph/companyPage/stockData.do',
    'X-Requested-With': 'XMLHttpRequest',
    'Connection': 'keep-alive'
}

TODAY_STR = datetime.today().strftime("%m-%d-%Y")


def run_downloader(input_csv="finalstocks.csv", output_dir="historicaldata"):
    """
    Fetches and stores historical data for each stock listed in the input CSV.
    """
    os.makedirs(output_dir, exist_ok=True)

    with open(input_csv, encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for count, row in enumerate(reader, start=1):
            company_id = row['companyId']
            security_id = row['securityId']
            company_name = row['companyName']
            stock_symbol = row['stockSymbol']

            print(f"[{count}] {company_id} {security_id} {stock_symbol} {company_name}")

            payload = {
                "cmpy_id": company_id,
                "security_id": security_id,
                "startDate": "01-01-1900",
                "endDate": TODAY_STR
            }

            try:
                response = requests.post(REQUEST_PATH, json=payload, headers=HEADERS)
                response.raise_for_status()
                hist_data = response.json()
                hist_values = hist_data.get('chartData', [])

                if not hist_values:
                    print(f"No data for {company_name}")
                    continue

                clean_name = company_name.replace('/', '-').replace('\\', '-').replace('&amp;', 'and')
                filename = os.path.join(output_dir, f"{stock_symbol}_{clean_name}.csv")

                with open(filename, 'w', newline='', encoding='utf-8') as company_file:
                    writer = csv.writer(company_file)
                    writer.writerow(['Date', 'Symbol', 'Value', 'Open', 'Close', 'High', 'Low'])

                    for item in hist_values:
                        date_obj = datetime.strptime(item['CHART_DATE'], '%b %d, %Y 00:00:00')
                        shortdate = date_obj.strftime("%d/%m/%Y")
                        writer.writerow([
                            shortdate,
                            stock_symbol,
                            item['VALUE'],
                            item['OPEN'],
                            item['CLOSE'],
                            item['HIGH'],
                            item['LOW']
                        ])

                print(f"Saved: {filename}")

            except requests.RequestException as e:
                print(f"Request failed for {company_name}: {e}")
            except (KeyError, ValueError) as e:
                print(f"Error processing {company_name}: {e}")