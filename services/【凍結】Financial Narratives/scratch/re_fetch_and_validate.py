import sys
import asyncio
import json
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.append(str(Path.cwd()))

from src.edgar_fetcher import EdgarFetcher
from src.config import USER_AGENT
from unstructured.partition.html import partition_html
import re

async def main():
    fetcher = EdgarFetcher(user_agent=USER_AGENT)
    ticker = "NVDA"
    
    print(f"Fetching latest 10-K/10-Q for {ticker}...")
    # 最新の提出書類リストを取得
    subs = await asyncio.to_thread(fetcher.get_latest_submissions, ticker)
    if not subs:
        print("No submissions found.")
        return
        
    filings = fetcher.filter_relevant_filings(subs)
    target = None
    for f in filings:
        if f['form'] in ['10-K', '10-Q']:
            target = f
            break
            
    cik = fetcher.ticker_to_cik_map.get(ticker)
    if not cik:
        print(f"CIK not found for {ticker}")
        return
        
    url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{target['accessionNumber'].replace('-', '')}/{target['primaryDocument']}"
    print(f"Downloading: {url}")
    
    import requests
    resp = await asyncio.to_thread(requests.get, url, headers={"User-Agent": USER_AGENT})
    if resp.status_code != 200:
        print(f"Download failed: {resp.status_code}")
        return
    
    html_content = resp.text

    print(f"HTML Downloaded ({len(html_content)} chars). Starting Unstructured partition...")
    
    # unstructuredによる解析
    elements = partition_html(text=html_content)
    print(f"Total Elements Found: {len(elements)}")
    
    sections = {}
    current_section = "preamble"
    current_content = []
    
    # SEC書類のセクション見出しパターン
    item_regex = re.compile(r"^\s*(ITEM|PART)\s+[0-9A-Z]+[\.\:\s]", re.IGNORECASE)
    
    for el in elements:
        text = str(el).strip()
        if not text:
            continue
            
        # 見出し判定の強化
        # UnstructuredのElementタイプ（Titleなど）も参考にできるが、
        # ここではテキストパターンで判定
        if item_regex.match(text) and len(text) < 150:
            if current_content:
                sections[current_section] = "\n".join(current_content)
            
            current_section = re.sub(r"[^a-z0-9]", "_", text.lower()).strip("_")
            current_content = []
            print(f"  [Detected Section]: {text}")
        else:
            current_content.append(text)
            
    if current_content:
        sections[current_section] = "\n".join(current_content)
        
    print(f"\n--- Extraction Summary ---")
    print(f"Market: US | Ticker: {ticker} | Form: {target['form']}")
    print(f"Total Sections Split: {len(sections)}")
    print(f"Section Keys: {list(sections.keys())}")
    
    # 内容の確認
    for key in ['item_1_business', 'item_7_management_s_discussion', 'item_1a_risk_factors']:
        match = [k for k in sections.keys() if key in k]
        if match:
            print(f"\n[Preview of {match[0]}]:")
            print(sections[match[0]][:500] + "...")
        else:
            print(f"\n[MISSING]: {key}")

if __name__ == "__main__":
    asyncio.run(main())
