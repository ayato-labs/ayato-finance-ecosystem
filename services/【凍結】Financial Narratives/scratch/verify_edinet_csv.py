import os
import io
import zipfile
import csv
from src.edinet_fetcher import EdinetFetcher
from src.storage import FinancialNarrativeStorage

def verify_csv_content():
    fetcher = EdinetFetcher()
    # 検証対象: 3399 (丸千代山岡家), 7203 (トヨタ), 9984 (ソフトバンク)
    # これら直近の有報 DocID (概算) を使用
    targets = [
        {"ticker": "3399", "doc_id": "S100Y1KO", "name": "丸千代山岡家"},
        {"ticker": "7203", "doc_id": "S100T72D", "name": "トヨタ"}, # 2024年有報例
        {"ticker": "9984", "doc_id": "S100T8G0", "name": "ソフトバンクG"}
    ]

    print("# EDINET CSV Content Verification\n")

    for target in targets:
        print(f"## Checking {target['name']} ({target['ticker']}) | DocID: {target['doc_id']}")
        try:
            # type=5 (CSV) をリクエスト
            csv_zip = fetcher.download_document(target["doc_id"], doc_type=5)
            if not csv_zip:
                print(f"FAILED: Could not download CSV for {target['ticker']}")
                continue

            with zipfile.ZipFile(io.BytesIO(csv_zip)) as z:
                csv_files = [f for f in z.namelist() if f.endswith(".csv")]
                print(f"Found {len(csv_files)} CSV files in ZIP.")
                
                narrative_found = False
                for csv_file in csv_files:
                    with z.open(csv_file) as f:
                        # EDINET CSV is often UTF-16 with BOM
                        content = f.read().decode("utf-16", errors="ignore")
                        reader = csv.reader(io.StringIO(content), delimiter="\t")
                        rows = list(reader)
                        
                        # カラム数や長い文字列の有無を確認
                        for row in rows:
                            for cell in row:
                                if len(cell) > 500: # 500文字以上のセルがあれば「定性情報あり」とみなす
                                    print(f"  [!] Narrative snippet found in {csv_file} (Length: {len(cell)})")
                                    print(f"      Preview: {cell[:100]}...")
                                    narrative_found = True
                                    break
                            if narrative_found: break
                
                if not narrative_found:
                    print("  [Result] NO qualitative narratives found in any CSV file. (Numeric only)")
                    
        except Exception as e:
            print(f"ERROR processing {target['ticker']}: {e}")
        print("\n---\n")

if __name__ == "__main__":
    verify_csv_content()
