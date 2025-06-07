"""
Combines all individual historical CSV files into a single combined CSV file.
"""

import os
import csv
import glob


def run_combiner(data_folder='historicaldata', output_file='combined.csv'):
    """
    Combines all CSV files in a folder into one output file.
    """
    csv_files = glob.glob(os.path.join(data_folder, '*.csv'))

    with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
        writer = csv.writer(outfile)
        writer.writerow(['Symbol', 'Company', 'Date', 'Value', 'Open', 'Close', 'High', 'Low'])

        for file in csv_files:
            filename = os.path.splitext(os.path.basename(file))[0]
            try:
                symbol, company = filename.split('_', 1)
            except ValueError:
                print(f"Skipping malformed filename: {filename}")
                continue

            with open(file, 'r', encoding='utf-8') as infile:
                reader = csv.reader(infile)
                next(reader, None)

                for row in reader:
                    writer.writerow([row[1], company, row[0], row[2], row[3], row[4], row[5], row[6]])

    print(f"All files combined into: {output_file}")