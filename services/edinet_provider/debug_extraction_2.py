import duckdb
import edinet_tools
import os
import sys
from loguru import logger
from src.core.config import settings
import datetime

def test_extraction():
    edinet_tools.configure(api_key=settings.EDINET_API_KEY)
    
    # Get a date where we know a 030000 exists
    conn = duckdb.connect('data/edinet.duckdb')
    row = conn.execute("SELECT CAST(submit_datetime AS DATE) FROM filings WHERE form_code = '030000' LIMIT 1").fetchone()
    conn.close()
    
    target_date = row[0]
    docs = edinet_tools.documents(date=target_date)
    target_doc = next(d for d in docs if d._data.get("formCode") == "030000")
    
    print(f"Testing extraction for {target_doc._data.get('filerName')} ({target_doc._data.get('docID')})")
    report = target_doc.parse()
    
    if report:
        print(f"Text Blocks Keys: {report.text_blocks.keys() if hasattr(report, 'text_blocks') else 'N/A'}")
        if hasattr(report, 'text_blocks'):
            for k, v in report.text_blocks.items():
                print(f"Block: {k} (Length: {len(str(v))})")
                if "リスク" in k or "経営方針" in k:
                    print(f"Sample: {str(v)[:100]}...")
    else:
        print("Failed to parse report.")

if __name__ == "__main__":
    test_extraction()
