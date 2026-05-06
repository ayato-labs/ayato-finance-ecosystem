import sys
import os
import json
import re
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.append(str(Path.cwd()))

from src.edgar_parser import EdgarParser
from src.storage import FinancialNarrativeStorage

def test_current_logic(html_content):
    parser = EdgarParser()
    sections = parser.extract_all_sections(html_content, "10-K")
    return sections

def test_unstructured_logic(html_content):
    try:
        from unstructured.partition.html import partition_html
        from unstructured.cleaners.core import clean
        
        # unstructuredでHTMLを要素（Elements）に分解
        elements = partition_html(text=html_content)
        
        sections = {}
        current_section = "preamble"
        current_content = []
        
        # 見出し（NarrativeTextやTitle）からItem X.を抽出する試み
        # SEC書類の一般的なパターン
        item_regex = re.compile(r"^(ITEM|PART)\s+[0-9A-Z]+[\.\:]", re.IGNORECASE)
        
        for el in elements:
            text = str(el).strip()
            if not text:
                continue
                
            # 見出しっぽいものを検出
            if item_regex.match(text) and len(text) < 100:
                # 前のセクションを保存
                if current_content:
                    sections[current_section] = "\n".join(current_content)
                
                current_section = re.sub(r"[^a-z0-9]", "_", text.lower()).strip("_")
                current_content = []
            else:
                current_content.append(text)
        
        # 最後のセクション
        if current_content:
            sections[current_section] = "\n".join(current_content)
            
        return sections
    except ImportError:
        return {"error": "unstructured not installed"}
    except Exception as e:
        return {"error": str(e)}

def validate():
    # 生データの取得 (storageのバックアップ用RawDataテーブルから)
    storage = FinancialNarrativeStorage("data/narratives_us.duckdb")
    
    # 以前の実験で raw_content を保存していない可能性があるため、
    # もし保存されていなければ sections の中身から再現を試みるか、
    # 別のソース（ファイル）から読み込む。
    # ここでは既存DBにあるNVDAのデータを取得
    with storage._connect(read_only=True) as conn:
        row = conn.execute("SELECT accession_number FROM filings WHERE ticker = 'NVDA' LIMIT 1").fetchone()
        if not row:
            print("NVDA data not found in DB.")
            return
        acc_no = row[0]
        
    # 本来はRawデータを検証すべきだが、まずは現状のパース済み結果を確認
    current_sections = storage.get_sections(acc_no)
    
    print(f"--- Validation for {acc_no} ---")
    print(f"Current Logic (Existing in DB): Found {len(current_sections)} sections")
    print(f"Keys: {list(current_sections.keys())}")
    
    # 比較のため、今回はテスト用の短いHTMLで挙動を確認（生HTMLの抽出が間に合わない場合）
    sample_html = """
    <html><body>
        <div><h1>ITEM 1. BUSINESS</h1><p>NVIDIA is a leader in accelerated computing.</p></div>
        <div><h1>ITEM 1A. RISK FACTORS</h1><p>Our business is subject to risks.</p></div>
        <div><h1>ITEM 7. MANAGEMENT'S DISCUSSION</h1><p>Revenue increased by 50%.</p></div>
    </body></html>
    """
    
    print("\n--- Comparative Test with Sample HTML ---")
    curr_res = test_current_logic(sample_html)
    unstr_res = test_unstructured_logic(sample_html)
    
    print(f"Current Logic: {list(curr_res.keys())}")
    print(f"Unstructured: {list(unstr_res.keys())}")
    
    if unstr_res:
        first_key = list(unstr_res.keys())[0]
        print(f"\n[Unstructured Sample Content - {first_key}]:")
        print(unstr_res[first_key][:200])

if __name__ == "__main__":
    validate()
