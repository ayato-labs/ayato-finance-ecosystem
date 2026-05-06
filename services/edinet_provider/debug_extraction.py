from src.core.config import settings
from src.core.csv_parser import get_csv_from_edinet, parse_edinet_csv
from loguru import logger

def debug_mufg_csv():
    # Nitori Holdings Annual Report
    doc_id = "S100LBVH" 
    api_key = settings.EDINET_API_KEY
    
    logger.info(f"Debugging CSV for {doc_id}...")
    content = get_csv_from_edinet(doc_id, api_key)
    if not content:
        logger.error("Failed to download CSV content")
        return
    
    csv_data = parse_edinet_csv(content)
    logger.info(f"Found {len(csv_data)} CSV files in ZIP")
    
    for name, df in csv_data.items():
        if df is not None and not df.empty:
            print(f"\n--- File: {name} ---")
            print(f"Columns ({len(df.columns)}): {list(df.columns)}")
            print("First 5 rows:")
            print(df.head(5).to_string())
            print("-" * 40)
        else:
            print(f"\n--- File: {name} (Empty or None) ---")

if __name__ == "__main__":
    debug_mufg_csv()
