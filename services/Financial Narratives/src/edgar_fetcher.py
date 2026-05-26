import random
import time
from datetime import date

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
        self.cik_to_ticker_map = {}
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
                    self.cik_to_ticker_map[cik] = ticker
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

    def get_ticker_from_cik(self, cik: str) -> str | None:
        """CIKからティッカーを取得"""
        if not self.cik_to_ticker_map:
            self._refresh_ticker_map()
        # 10桁にパディングして検索
        return self.cik_to_ticker_map.get(str(cik).zfill(10))

    def list_daily_filings(
        self, target_date: date, target_forms: list[str] | None = None
    ) -> list[dict]:
        """
        SEC Daily Index (master.idx) を使用して、指定日の提出書類一覧を取得
        """
        if target_forms is None:
            target_forms = ["10-K", "10-Q"]

        year = target_date.year
        quarter = (target_date.month - 1) // 3 + 1
        date_str = target_date.strftime("%Y%m%d")

        url = (
            f"https://www.sec.gov/Archives/edgar/daily-index/"
            f"{year}/QTR{quarter}/master.{date_str}.idx"
        )

        logger.info(f"Fetching SEC Daily Index | date={target_date} | url={url}")
        response = self._request_with_retry(url)

        if not response or response.status_code != 200:
            logger.warning(
                f"No SEC index found for {target_date} (Weekend, holiday, or late update)"
            )
            return []

        lines = response.text.splitlines()
        data_start = 0
        for i, line in enumerate(lines):
            if line.startswith("---"):
                data_start = i + 1
                break

        if data_start == 0:
            logger.error(f"Malformed SEC index file for {target_date}")
            return []

        results = []
        for line in lines[data_start:]:
            parts = line.split("|")
            if len(parts) >= 5:
                cik = parts[0].zfill(10)
                form_type = parts[2]
                if form_type in target_forms:
                    # Filename format: edgar/data/1023731/0001023731-26-000041.txt
                    filename = parts[4]
                    acc_no = filename.split("/")[-1].replace(".txt", "")
                    doc_name = filename.split("/")[-1]  # Fallback primary document name

                    results.append(
                        {
                            "cik": cik,
                            "ticker": self.get_ticker_from_cik(cik),
                            "form": form_type,
                            "filingDate": parts[3],
                            "accessionNumber": acc_no,
                            "primaryDocument": doc_name,
                        }
                    )

        logger.info(f"Found {len(results)} relevant filings in daily index")
        return results

    def resolve_filing_metadata(self, ticker: str, accession_number: str) -> dict | None:
        """
        accessionNumber から正確な primaryDocument 名や説明を取得する
        """
        subs = self.get_latest_submissions(ticker)
        if not subs or "filings" not in subs:
            return None

        recent = subs["filings"]["recent"]
        for i in range(len(recent["accessionNumber"])):
            if recent["accessionNumber"][i] == accession_number:
                return {
                    "accessionNumber": recent["accessionNumber"][i],
                    "filingDate": recent["filingDate"][i],
                    "form": recent["form"][i],
                    "primaryDocument": recent["primaryDocument"][i],
                    "primaryDocDescription": recent["primaryDocDescription"][i],
                }
        return None

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
        """10-Kや10-Qなどの特定の書類のみを抽出"""
        try:
            if doc_types is None:
                doc_types = ["10-K", "10-Q"]
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
                        "primaryDocDescription": recent["primaryDocDescription"][i],
                    }
                    relevant_filings.append(filing)

            return relevant_filings
        except Exception:
            logger.exception("Error filtering relevant filings")
            return []


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
