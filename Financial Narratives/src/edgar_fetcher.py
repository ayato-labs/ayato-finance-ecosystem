import requests
import json
import time
from loguru import logger
from typing import Dict, List, Optional

class EdgarFetcher:
    """
    SEC EDGAR API から企業の提出書類情報を取得するクラス
    SECの規約に従い、User-Agentにはメールアドレスを含める必要があります。
    """
    
    BASE_URL_SUBMISSIONS = "https://data.sec.gov/submissions/"
    BASE_URL_TICKERS = "https://www.sec.gov/files/company_tickers.json"

    def __init__(self, user_agent: str):
        # User-Agent 例: "YourName yourname@example.com"
        self.headers = {"User-Agent": user_agent}
        self.ticker_to_cik_map = {}

    def _refresh_ticker_map(self):
        """ティッカーからCIKを変換するためのマスターリストを取得"""
        logger.info("Refreshing SEC ticker-to-cik map...")
        response = requests.get(self.BASE_URL_TICKERS, headers=self.headers)
        if response.status_code == 200:
            data = response.json()
            # dataは "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."} という形式
            for key in data:
                entry = data[key]
                ticker = entry["ticker"].upper()
                cik = str(entry["cik_str"]).zfill(10)
                self.ticker_to_cik_map[ticker] = cik
        else:
            logger.error(f"Failed to fetch ticker map: {response.status_code}")

    def get_cik(self, ticker: str) -> Optional[str]:
        """ティッカーから10桁のCIKを取得"""
        ticker = ticker.upper()
        if not self.ticker_to_cik_map:
            self._refresh_ticker_map()
        return self.ticker_to_cik_map.get(ticker)

    def get_latest_submissions(self, ticker: str) -> Optional[Dict]:
        """特定の企業の最新の提出書類リストを取得"""
        cik = self.get_cik(ticker)
        if not cik:
            logger.warning(f"CIK not found for ticker: {ticker}")
            return None

        url = f"{self.BASE_URL_SUBMISSIONS}CIK{cik}.json"
        logger.info(f"Fetching submissions for {ticker} (CIK: {cik})...")
        
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to fetch submissions for {ticker}: {response.status_code}")
            return None

    def filter_relevant_filings(self, submissions_data: Dict, doc_types: List[str] = ["10-K", "10-Q"]) -> List[Dict]:
        """10-Kや10-Qなどの特定の書類のみを抽出"""
        if not submissions_data or "filings" not in submissions_data:
            return []

        recent = submissions_data["filings"]["recent"]
        relevant_filings = []
        
        for i in range(len(recent["form"])):
            if recent["form"][i] in doc_types:
                filing = {
                    "accessionNumber": recent["accessionNumber"][i],
                    "filingDate": recent["filingDate"][i],
                    "form": recent["form"][i],
                    "primaryDocument": recent["primaryDocument"][i],
                    "description": recent["primaryDocDescription"][i]
                }
                relevant_filings.append(filing)
        
        return relevant_filings

if __name__ == "__main__":
    # テスト実行
    # NOTE: 実際のメールアドレスを入力することを推奨します
    fetcher = EdgarFetcher(user_agent="SampleAgent sample@example.com")
    
    ticker = "AAPL"
    subs = fetcher.get_latest_submissions(ticker)
    if subs:
        filings = fetcher.filter_relevant_filings(subs)
        logger.success(f"Found {len(filings)} relevant filings for {ticker}")
        for f in filings[:3]:  # 最新3件を表示
            logger.info(f"{f['filingDate']} - {f['form']}: {f['accessionNumber']}")
