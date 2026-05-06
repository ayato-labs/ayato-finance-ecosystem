from datetime import date, timedelta
from dotenv import load_dotenv
from src.edinet_fetcher import EdinetFetcher

load_dotenv()

def find_real_yuho():
    fetcher = EdinetFetcher()
    # 2024年6月末付近をスキャン
    for i in range(10):
        target_date = date(2024, 6, 20) + timedelta(days=i)
        print(f"Scanning {target_date}...")
        docs = fetcher.list_documents(target_date)
        if not docs: continue
        
        yuhos = [d for d in docs if d.get("formCode") == "030000"]
        if yuhos:
            print(f"Found {len(yuhos)} Yuhos on {target_date}.")
            for d in yuhos[:5]:
                print(f" - {d.get('filerName')} ({d.get('secCode')}): {d.get('docID')}")
            return # 1件見つかればOK


if __name__ == "__main__":
    find_real_yuho()
