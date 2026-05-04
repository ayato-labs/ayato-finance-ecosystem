import random
import time

import requests
from loguru import logger


class EdgarFetcher:
    """
    SEC EDGAR API から企業の提出書類情報を取得するクラス
    SECの規約に従い、User-Agentにはメールアドレスを含める必要があります。
    """

    BASE_URL_SUBMISSIONS = "https://data.sec.gov/submissions/"
    BASE_URL_TICKERS = "https://www.sec.gov/files/company_tickers.json"

    def __init__(self, user_agent: str, max_retries: int = 5):
        # User-Agent 例: "YourName yourname@example.com"
        self.headers = {"User-Agent": user_agent}
        self.ticker_to_cik_map = {}
        self.max_retries = max_retries

    def _request_with_retry(self, url: str) -> requests.Response | None:
        """SEC APIへのリクエストを指数バックオフ付きで実行"""
        for attempt in range(self.max_retries):
            try:
                response = requests.get(url, headers=self.headers, timeout=15)

                if response.status_code == 200:
                    return response

                if response.status_code == 429:
                    # SECの制限に達した場合
                    wait_time = (2**attempt) + random.uniform(0, 1)
                    logger.warning(
                        f"SEC Rate Limit (429). Retrying in {wait_time:.2f}s... "
                        f"(Attempt {attempt + 1}/{self.max_retries})"
                    )
                    time.sleep(wait_time)
                    continue

                if response.status_code >= 500:
                    # サーバーエラー
                    wait_time = (2**attempt) + random.uniform(0, 1)
                    logger.error(
                        f"SEC Server Error ({response.status_code}). "
                        f"Retrying in {wait_time:.2f}s..."
                    )
                    time.sleep(wait_time)
                    continue

                # その他のエラー (404, 403等) はリトライせず終了
                logger.error(f"SEC API Error: {response.status_code} for {url}")
                return None

            except requests.RequestException as e:
                wait_time = (2**attempt) + random.uniform(0, 1)
                logger.error(f"Network error: {e}. Retrying in {wait_time:.2f}s...")
                time.sleep(wait_time)

        logger.error(f"Max retries reached for {url}")
        return None

    def _refresh_ticker_map(self):
        """ティッカーからCIKを変換するためのマスターリストを取得"""
        logger.info("Refreshing SEC ticker-to-cik map...")
        response = self._request_with_retry(self.BASE_URL_TICKERS)
        if response and response.status_code == 200:
            data = response.json()
            # dataは "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."} という形式
            for key in data:
                entry = data[key]
                ticker = entry["ticker"].upper()
                cik = str(entry["cik_str"]).zfill(10)
                self.ticker_to_cik_map[ticker] = cik
        else:
            status = response.status_code if response else "N/A"
            logger.error(f"Failed to fetch ticker map: {status}")

    def get_all_tickers(self) -> list[str]:
        """全ティッカーのリストを取得"""
        if not self.ticker_to_cik_map:
            self._refresh_ticker_map()
        return list(self.ticker_to_cik_map.keys())

    def get_cik(self, ticker: str) -> str | None:
        """ティッカーから10桁のCIKを取得"""
        ticker = ticker.upper()
        if not self.ticker_to_cik_map:
            self._refresh_ticker_map()
        return self.ticker_to_cik_map.get(ticker)

    def get_latest_submissions(self, ticker: str) -> dict | None:
        """特定の企業の最新の提出書類リストを取得"""
        cik = self.get_cik(ticker)
        if not cik:
            logger.warning(f"CIK not found for ticker: {ticker}")
            return None

        url = f"{self.BASE_URL_SUBMISSIONS}CIK{cik}.json"
        logger.info(f"Fetching submissions for {ticker} (CIK: {cik})...")

        response = self._request_with_retry(url)
        if response and response.status_code == 200:
            return response.json()
        return None

    def filter_relevant_filings(
        self, submissions_data: dict, doc_types: list[str] = ["10-K", "10-Q"]
    ) -> list[dict]:
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
                    "description": recent["primaryDocDescription"][i],
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
