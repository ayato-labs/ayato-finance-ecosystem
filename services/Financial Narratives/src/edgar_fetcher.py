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
                        f"SEC Rate Limit (429) | url={url} | retry_in={wait_time:.2f}s | "
                        f"attempt={attempt + 1}/{self.max_retries}"
                    )
                    time.sleep(wait_time)
                    continue

                if response.status_code >= 500:
                    # サーバーエラー
                    wait_time = (2**attempt) + random.uniform(0, 1)
                    logger.error(
                        f"SEC Server Error ({response.status_code}) | url={url} | "
                        f"retry_in={wait_time:.2f}s | attempt={attempt + 1}/{self.max_retries}"
                    )
                    time.sleep(wait_time)
                    continue

                # その他のエラー (404, 403等) はリトライせず終了
                logger.error(f"SEC API Error | status={response.status_code} | url={url}")
                return None

            except requests.RequestException:
                wait_time = (2**attempt) + random.uniform(0, 1)
                logger.exception(
                    f"Network error during SEC request | url={url} | retry_in={wait_time:.2f}s"
                )
                time.sleep(wait_time)

        logger.error(f"Max retries reached for SEC API | url={url}")
        return None

    def _refresh_ticker_map(self):
        """ティッカーからCIKを変換するためのマスターリストを取得"""
        try:
            logger.info("Refreshing SEC ticker-to-cik map")
            response = self._request_with_retry(self.BASE_URL_TICKERS)
            if response and response.status_code == 200:
                data = response.json()
                for key in data:
                    entry = data[key]
                    ticker = entry["ticker"].upper()
                    cik = str(entry["cik_str"]).zfill(10)
                    self.ticker_to_cik_map[ticker] = cik
                logger.info(f"Ticker map refreshed | count={len(self.ticker_to_cik_map)}")
            else:
                status = response.status_code if response else "N/A"
                logger.error(f"Failed to fetch ticker map | status={status}")
        except Exception:
            logger.exception("Failed to refresh SEC ticker map")

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
        try:
            cik = self.get_cik(ticker)
            if not cik:
                logger.warning(f"CIK not found for ticker | ticker={ticker}")
                return None

            url = f"{self.BASE_URL_SUBMISSIONS}CIK{cik}.json"
            logger.info(f"Fetching submissions | ticker={ticker} | cik={cik}")

            response = self._request_with_retry(url)
            if response and response.status_code == 200:
                return response.json()
            return None
        except Exception:
            logger.exception(f"Error fetching submissions | ticker={ticker}")
            return None

    def filter_relevant_filings(
        self, submissions_data: dict, doc_types: list[str] | None = None
    ) -> list[dict]:
        """特定の書類を抽出（doc_typesがNoneまたは空の場合は全書類を返す）"""
        try:
            if not submissions_data or "filings" not in submissions_data:
                return []

            recent = submissions_data["filings"]["recent"]
            relevant_filings = []

            for i in range(len(recent["form"])):
                if doc_types is None or len(doc_types) == 0 or recent["form"][i] in doc_types:
                    filing = {
                        "accessionNumber": recent["accessionNumber"][i],
                        "filingDate": recent["filingDate"][i],
                        "form": recent["form"][i],
                        "primaryDocument": recent["primaryDocument"][i],
                        "primaryDocDescription": recent["primaryDocDescription"][i],
                    }
                    relevant_filings.append(filing)

            return relevant_filings
        except Exception:
            logger.exception("Error filtering relevant filings")
            return []

    def get_recent_filings_from_index(self, days: int = 2) -> list[dict]:
        """
        SECのデイリーインデックス(XBRL)を使用して、直近の提出書類を効率的に取得する。
        全ティッカーをスキャンする代わりに、このインデックスを使用することでリクエスト数を劇的に削減できる。
        """
        import datetime
        from bs4 import BeautifulSoup
        
        recent_filings = []
        today = datetime.date.today()
        
        # 10桁のCIKからティッカーを引くための逆引きマップを準備
        if not self.ticker_to_cik_map:
            self._refresh_ticker_map()
        cik_to_ticker = {v: k for k, v in self.ticker_to_cik_map.items()}
        
        # 逆順（新しい順）にチェック
        for i in range(days):
            target_date = today - datetime.timedelta(days=i)
            # 例: https://www.sec.gov/Archives/edgar/daily-index/xbrl/xbrlrss.20240501.xml
            date_str = target_date.strftime("%Y%m%d")
            url = f"https://www.sec.gov/Archives/edgar/daily-index/xbrl/xbrlrss.{date_str}.xml"
            
            logger.info(f"Checking SEC daily index | date={date_str} | url={url}")
            response = self._request_with_retry(url)
            
            if not response or response.status_code != 200:
                continue
                
            try:
                soup = BeautifulSoup(response.content, "xml")
                items = soup.find_all("item")
                
                for item in items:
                    xbrl_filing = item.find("edgar:xbrlFiling")
                    if not xbrl_filing:
                        continue
                        
                    form = xbrl_filing.find("edgar:formType").text
                    cik = xbrl_filing.find("edgar:cikNumber").text.zfill(10)
                    acc_no = xbrl_filing.find("edgar:accessionNumber").text
                    
                    actual_ticker = cik_to_ticker.get(cik, f"CIK{cik}")
                        
                    recent_filings.append({
                        "accessionNumber": acc_no,
                        "ticker": actual_ticker,
                        "cik": cik,
                        "form": form,
                        "filingDate": target_date.isoformat(),
                        "primaryDocument": item.find("link").text.split("/")[-1]
                    })
            except Exception:
                logger.exception(f"Error parsing SEC daily index for {date_str}")
                
        logger.info(f"Discovery completed | found {len(recent_filings)} potential filings in index")
        return recent_filings


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
