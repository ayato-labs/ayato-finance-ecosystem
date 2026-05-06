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
    
    if not row:
        print("No Annual Report (030000) found in DB.")
        return

    target_date = row[0]
    print(f"Target date for search: {target_date}")
    
    try:
        # Search for documents on that date
        docs = edinet_tools.documents(date=target_date)
        target_doc = None
        for d in docs:
            if d._data.get("formCode") == "030000":
                target_doc = d
                break
        
        if not target_doc:
            print(f"Could not find 030000 document on {target_date} via API.")
            return

        print(f"Testing extraction for {target_doc._data.get('filerName')} ({target_doc._data.get('docID')})")
        
        # This is what engine.py does
        report = target_doc.parse()
        print(f"Parse result: {report}")
        
        if report:
            biz = getattr(report, "business", None)
            print(f"Business object: {biz}")
            if biz:
                print(f"Risks: {getattr(biz, 'risks', 'None')}")
                print(f"Policy: {getattr(biz, 'policy_environment_issue_etc', 'None')}")
                print(f"Analysis: {getattr(biz, 'analysis_of_financial_results', 'None')}")
            else:
                print(f"Report attributes: {dir(report)}")
                # Check for other common attributes like 'financial_statements'
                print(f"Has financial_statements? {hasattr(report, 'financial_statements')}")
        else:
            print("Failed to parse report (returned None).")

    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_extraction()
