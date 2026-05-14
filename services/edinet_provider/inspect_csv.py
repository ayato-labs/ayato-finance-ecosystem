import io
import zipfile
import pandas as pd
from src.service.csv_parser import get_csv_from_edinet, parse_edinet_csv
from src.infra.config import settings

doc_id = "S100LL94"
api_key = "1b0a97354f104bdbb5e609eccaec7a64" # From .env

print(f"Fetching CSV for {doc_id}...")
content = get_csv_from_edinet(doc_id, api_key)
if not content:
    print("Failed to fetch content.")
    exit(1)

csv_data = parse_edinet_csv(content)
print(f"Found {len(csv_data)} CSV files.")

for file_name, df in csv_data.items():
    print(f"\n--- {file_name} ---")
    print(f"Columns: {df.columns.tolist()}")
    # Look for 'CurrentFiscalYearEndDateDEI' or similar
    matches = df[df.iloc[:, 0].astype(str).str.contains('FiscalYear', na=False)]
    if not matches.empty:
        print("Matches found:")
        print(matches.iloc[:, [0, 1, 8]].to_string()) # ID, Name, Value
