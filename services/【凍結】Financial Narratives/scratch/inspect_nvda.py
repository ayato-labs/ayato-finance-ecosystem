from src.storage import FinancialNarrativeStorage
import json

def inspect():
    storage = FinancialNarrativeStorage("data/narratives_us.duckdb")
    # NVDAの最新の書類を取得
    with storage._connect(read_only=True) as conn:
        row = conn.execute("SELECT accession_number, ticker FROM filings WHERE ticker = 'NVDA' ORDER BY filing_date DESC LIMIT 1").fetchone()
        if not row:
            print("NVDA not found.")
            return
        acc_no, ticker = row
    
    sections = storage.get_sections(acc_no)
    print(f"Ticker: {ticker} | AccNo: {acc_no}")
    print(f"Available Sections: {list(sections.keys())}")
    
    for k, v in sections.items():
        if "Business" in k or "MD&A" in k or "Management's Discussion" in k or "Risk" in k:
            print(f"\n--- Section: {k} ---")
            print(v[:1000]) # 冒頭1000文字
            print("-" * 20)

if __name__ == "__main__":
    inspect()
