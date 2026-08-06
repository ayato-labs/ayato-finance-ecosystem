import random
import time
from datetime import date

import requests
from loguru import logger


class EdgarFetcher:
    """
    SEC EDGAR API から企業のメタデータや提出書類（Filing）の一覧を取得する通信クライアントクラス。
    SECの利用規約（User-Agentに有効なメールアドレスを含めること、1秒あたり10リクエスト以下の制御）に対応します。
    """

    BASE_URL_SUBMISSIONS = "https://data.sec.gov/submissions/"
    BASE_URL_TICKERS = "https://www.sec.gov/files/company_tickers.json"

    def __init__(self, user_agent: str, max_retries: int = 5):
        # User-Agent 例: "YourName yourname@example.com" (SECへのアクセスに必須)
        self.headers = {"User-Agent": user_agent}
        self.ticker_to_cik_map = {}
        self.cik_to_ticker_map = {}
        self.max_retries = max_retries

    def _request_with_retry(self, url: str) -> requests.Response | None:
        """SEC APIへのHTTPリクエストを、エラー時の指数バックオフ付きで実行します。"""
        for attempt in range(self.max_retries):
            try:
                response = requests.get(url, headers=self.headers, timeout=15)

                if response.status_code == 200:
                    return response

                # SEC のアクセス制限（Rate Limit）である 429 エラーを受信した場合
                if response.status_code == 429:
                    # 指数バックオフ＋ランダムな揺らぎ時間でウェイトを入れて再試行
                    wait_time = (2**attempt) + random.uniform(0, 1)
                    logger.warning(
                        f"SEC Rate Limit (429) | url={url} | retry_in={wait_time:.2f}s | "
                        f"attempt={attempt + 1}/{self.max_retries}"
                    )
                    time.sleep(wait_time)
                    continue

                # 5xx 系のサーバーエラーの場合
                if response.status_code >= 500:
                    wait_time = (2**attempt) + random.uniform(0, 1)
                    logger.error(
                        f"SEC Server Error ({response.status_code}) | url={url} | "
                        f"retry_in={wait_time:.2f}s | attempt={attempt + 1}/{self.max_retries}"
                    )
                    time.sleep(wait_time)
                    continue

                # その他のエラー (404, 403等) は修復不可能と判断しリトライせず終了
                logger.error(f"SEC API Error | status={response.status_code} | url={url}")
                return None

            except requests.RequestException:
                # ネットワーク切断などの例外発生時もリトライを実行
                wait_time = (2**attempt) + random.uniform(0, 1)
                logger.exception(
                    f"Network error during SEC request | url={url} | retry_in={wait_time:.2f}s"
                )
                time.sleep(wait_time)

        logger.error(f"Max retries reached for SEC API | url={url}")
        return None

    def _refresh_ticker_map(self):
        """SECから上場企業全銘柄の「ティッカーシンボル ⇔ CIK」マッピングマスタを取得し、メモリ内にキャッシュします。"""
        try:
            logger.info("Refreshing SEC ticker-to-cik map")
            response = self._request_with_retry(self.BASE_URL_TICKERS)
            if response and response.status_code == 200:
                data = response.json()
                for key in data:
                    entry = data[key]
                    ticker = entry["ticker"].upper()
                    # CIK（企業固有コード）は10桁のゼロパディング形式で統一
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
        """SECマスタに登録されているすべてのティッカーのリストを取得します。"""
        if not self.ticker_to_cik_map:
            self._refresh_ticker_map()
        return list(self.ticker_to_cik_map.keys())

    def get_cik(self, ticker: str) -> str | None:
        """与えられたティッカーシンボルから10桁の CIK を解決します。"""
        ticker = ticker.upper()
        if not self.ticker_to_cik_map:
            self._refresh_ticker_map()
        return self.ticker_to_cik_map.get(ticker)

    def get_ticker_from_cik(self, cik: str) -> str | None:
        """与えられた CIK（企業コード）からティッカーシンボルを解決します。"""
        if not self.cik_to_ticker_map:
            self._refresh_ticker_map()
        return self.cik_to_ticker_map.get(str(cik).zfill(10))

    def list_daily_filings(
        self, target_date: date, target_forms: list[str] | None = None
    ) -> list[dict]:
        """
        SEC Daily Index (master.idx) から、指定日に提出されたすべての報告書リストを取得し、
        さらに 10-K / 10-Q に該当する開示資料だけをフィルタリングして返します。
        """
        if target_forms is None:
            target_forms = ["10-K", "10-Q"]

        year = target_date.year
        quarter = (target_date.month - 1) // 3 + 1
        date_str = target_date.strftime("%Y%m%d")

        # SEC Daily Index アーカイブURLの構築
        url = (
            f"https://www.sec.gov/Archives/edgar/daily-index/"
            f"{year}/QTR{quarter}/master.{date_str}.idx"
        )

        logger.info(f"Fetching SEC Daily Index | date={target_date} | url={url}")
        response = self._request_with_retry(url)

        if not response or response.status_code != 200:
            # 土日祝日や、SEC側の遅延更新などの場合は提出リストなしとして処理
            logger.warning(
                f"No SEC index found for {target_date} (Weekend, holiday, or late update)"
            )
            return []

        # インデックスファイルはパイプ記号 '|' 区切りのプレーンテキスト
        lines = response.text.splitlines()
        data_start = 0
        # ヘッダー行をスキップし、データ開始点を見つける
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
                    # ファイルパスの形式: edgar/data/1023731/0001023731-26-000041.txt
                    filename = parts[4]
                    acc_no = filename.split("/")[-1].replace(".txt", "")
                    doc_name = filename.split("/")[-1]  # プライマリドキュメント名のフォールバック用

                    ticker = self.get_ticker_from_cik(cik) or "UNKNOWN"
                    results.append(
                        {
                            "cik": cik,
                            "ticker": ticker,
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
        特定の書類の accessionNumber を元に、正確な一次提出ドキュメント名（例: primaryDocument: 'aapl-20251025.htm'）や
        その解説文をSECの直近提出メタデータエンドポイントから特定して解決します。
        """
        subs = self.get_latest_submissions(ticker)
        if not subs or "filings" not in subs:
            return None

        recent = subs["filings"]["recent"]
        # 受付番号が一致する項目を線形探索
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

    def fetch_filing_content(self, cik: str, accession_number: str, primary_document: str) -> str | None:
        """
        指定された CIK, accessionNumber, primaryDocument を元に、
        SECから提出書類の本文（HTML等）を取得します。
        """
        acc_no_clean = accession_number.replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no_clean}/{primary_document}"
        logger.debug(f"Downloading filing content | url={url}")
        response = self._request_with_retry(url)
        if response and response.status_code == 200:
            return response.text
        return None

    def get_latest_submissions(self, ticker: str) -> dict | None:
        """指定したティッカー企業の、SECに登録されているすべての最近の開示資料情報を取得します。"""
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
        """取得した全開示リストの中から、10-K（通期有報）および10-Q（四半期有報）のみを抽出・フィルタリングします。"""
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
