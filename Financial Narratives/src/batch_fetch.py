import time
import requests
from pathlib import Path
from loguru import logger
from .edgar_fetcher import EdgarFetcher
from .edgar_parser import EdgarParser
from .storage import FinancialNarrativeStorage

USER_AGENT = "SampleAgent yourname@example.com"
TICKERS = ["AAPL", "NVDA", "GOOGL", "AMZN", "META"]

def batch_fetch(tickers: list[str] = None):
    if tickers is None:
        tickers = TICKERS
        
    fetcher = EdgarFetcher(USER_AGENT)
    parser = EdgarParser()
    storage = FinancialNarrativeStorage()
    
    # 中間保存用ディレクトリ（オプション）
    raw_dir = Path("data/raw_json")
    raw_dir.mkdir(parents=True, exist_ok=True)

    for ticker in tickers:
        try:
            logger.info(f"=== Processing {ticker} ===")
            
            # 1. 提出書類リスト取得
            subs = fetcher.get_latest_submissions(ticker)
            if not subs: continue
            
            # 2. 最新10-K特定
            filings = fetcher.filter_relevant_filings(subs, doc_types=["10-K"])
            if not filings:
                logger.warning(f"No 10-K for {ticker}")
                continue
            
            latest = filings[0]
            acc_no = latest['accessionNumber']

            # 差分更新チェック: 既にDBに存在すればスキップ
            if storage.filing_exists(acc_no):
                logger.info(f"Filing {acc_no} already exists in DB. Skipping {ticker}.")
                continue

            cik = fetcher.get_cik(ticker).lstrip('0')
            acc_no_clean = acc_no.replace("-", "")
            doc = latest['primaryDocument']
            url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no_clean}/{doc}"
            
            # 3. ダウンロード
            logger.info(f"Downloading {ticker} 10-K: {url}")
            resp = requests.get(url, headers={"User-Agent": USER_AGENT})
            time.sleep(0.1) # SEC制限配慮
            
            if resp.status_code != 200:
                logger.error(f"Failed to download {ticker}: {resp.status_code}")
                continue
            
            # 4. パース (複数セクション抽出)
            sections = parser.extract_all_sections(resp.text, "10-K")
            
            if sections:
                # メタデータの整備
                filing_metadata = latest.copy()
                filing_metadata["ticker"] = ticker
                filing_metadata["cik"] = cik
                
                # DuckDBへ保存
                storage.save_filing(filing_metadata, sections)
                
                # セクションごとの抽出状況をログ出力
                found_keys = [k for k, v in sections.items() if v]
                logger.success(f"Extracted {len(found_keys)} sections for {ticker}: {', '.join(found_keys)}")
            else:
                logger.warning(f"No sections extracted for {ticker}")
            
            # SECレート制限(10 req/sec)を守るため待機
            time.sleep(0.5)

        except Exception as e:
            logger.error(f"Error processing {ticker}: {e}")

if __name__ == "__main__":
    batch_fetch()
