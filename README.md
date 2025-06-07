# PSE Data Scraper

**PSE Data Scraper** is a Python-based tool designed to collect and consolidate historical stock price data from the Philippine Stock Exchange (PSE) EDGE portal.

The script performs the following steps:

1. Scrapes a list of all listed companies and their stock symbols from the PSE website.
2. Downloads each company's full historical stock price data.
3. Saves the data as individual CSV files.
4. Merges all files into a single, consolidated CSV file suitable for further analysis.

---

## Requirements

- Python 3.7 or higher

Install the required dependencies using:

```bash
pip install -r requirements.txt
```

---

## Usage

To run the complete data scraping and consolidation process:

```bash
python main.py
```

This command will:

- Generate `finalstocks.csv` containing the company and stock symbol list
- Save one CSV per company inside the `historicaldata/` directory
- Produce a unified `combined.csv` containing all stock data

---

## Output Files

- `finalstocks.csv` — List of companies and stock symbols from PSE
- `historicaldata/` — Folder containing historical stock data per company
- `combined.csv` — Single CSV file with all company data combined

---

## Structure

```
pse-data-scraper/
│
├── main.py                  # Main script to execute the full process
├── requirements.txt         # Python package dependencies
├── LICENSE                  # Project license (MIT)
├── README.md                # Project documentation
├── .gitignore               # Files and folders excluded from version control
└── utils/
    ├── scraper.py           # Scrapes company and stock symbol data
    ├── downloader.py        # Downloads historical stock prices
    └── combiner.py          # Combines all CSVs into one
```

---

## Notes

- The script includes polite delays between requests.
- All data is sourced from endpoints provided by the PSE.

---

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
