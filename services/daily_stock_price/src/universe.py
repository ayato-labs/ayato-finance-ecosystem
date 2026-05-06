import io
import os
import re
import time
from http import HTTPStatus
from pathlib import Path

import pandas as pd
import requests
from loguru import logger

HTTP_OK = HTTPStatus.OK


class UniverseManager:
    def __init__(self, cache_dir: str = "./data/universe", fmp_api_key: str | None = None):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.fmp_api_key = fmp_api_key or os.getenv("FMP_API_KEY")

    def _is_cache_fresh(self, cache_file: Path, hours: int = 24) -> bool:
        """キャッシュファイルが存在し、指定時間以内かチェック"""
        if not cache_file.exists():
            return False
        mtime = cache_file.stat().st_mtime
        return (time.time() - mtime) < (hours * 3600)

    def get_jp_universe(self) -> list[str]:
        """
        JPXから日本株全銘柄のリストを取得。24時間キャッシュ。
        """
        cache_file = self.cache_dir / "jp_tickers.csv"
        if self._is_cache_fresh(cache_file):
            df = pd.read_csv(cache_file)
            return df["Ticker"].tolist()

        logger.info("Fetching JPX ticker list...")
        agent_str = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/119.0.0.0 Safari/537.36"
        )
        headers = {"User-Agent": agent_str}

        index_url = "https://www.jpx.co.jp/markets/statistics-equities/misc/01.html"
        try:
            resp = requests.get(index_url, headers=headers)
            matches = re.findall(r"href=\"(.*?data_j.xls)\"", resp.text)
            if not matches:
                raise ValueError("Could not find data_j.xls link.")

            xls_url = matches[0]
            if xls_url.startswith("/"):
                xls_url = "https://www.jpx.co.jp" + xls_url

            logger.info(f"Downloading JPX list from: {xls_url}")
            resp = requests.get(xls_url, headers=headers)
            df = pd.read_excel(io.BytesIO(resp.content))
            df["Ticker"] = df["コード"].astype(str) + ".T"

            # キャッシュ保存
            df[["Ticker", "銘柄名", "市場・商品区分"]].to_csv(cache_file, index=False)
            return df["Ticker"].tolist()
        except Exception as e:
            logger.error(f"Failed to fetch JPX tickers: {e}")
            return []

    def get_us_universe(self) -> list[str]:
        """
        NasdaqTrader または FMP から米国株全銘柄リストを取得。24時間キャッシュ。
        """
        cache_file = self.cache_dir / "us_tickers_full.csv"
        if self._is_cache_fresh(cache_file):
            df = pd.read_csv(cache_file)
            return df["Ticker"].tolist()

        all_tickers = []

        # FMP Keyがある場合は優先して使用
        if self.fmp_api_key:
            logger.info("Fetching US ticker list from FMP...")
            try:
                url = (
                    f"https://financialmodelingprep.com/api/v3/available-traded/list?"
                    f"apikey={self.fmp_api_key}"
                )
                resp = requests.get(url, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                # 米国市場の銘柄のみ抽出
                all_tickers = [
                    item["symbol"]
                    for item in data
                    if item.get("exchangeShortName") in ["NASDAQ", "NYSE", "AMEX"]
                ]
            except Exception as e:
                logger.error(f"Failed to fetch from FMP: {e}")

        # FMPで取得できなかった場合、NasdaqTraderから取得
        if not all_tickers:
            logger.info("Fetching full US ticker list from NasdaqTrader...")
            urls = [
                "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt",
                "https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt",
            ]
            headers = {"User-Agent": "Mozilla/5.0"}

            for url in urls:
                try:
                    resp = requests.get(url, headers=headers, timeout=15)
                    resp.raise_for_status()
                    lines = resp.text.splitlines()
                    clean_lines = [
                        line
                        for line in lines
                        if "|" in line and not line.startswith("File Creation Time")
                    ]
                    if not clean_lines:
                        continue

                    df = pd.read_csv(io.StringIO("\n".join(clean_lines)), sep="|")
                    col_name = "Symbol" if "Symbol" in df.columns else "NASDAQ Symbol"
                    if col_name in df.columns:
                        all_tickers.extend(df[col_name].dropna().astype(str).tolist())
                except Exception as e:
                    logger.error(f"Error fetching from {url}: {e}")

        # さらに取得できなかった場合、WikipediaからS&P 500等をフォールバックとして取得 (テスト用)
        if not all_tickers:
            logger.info("Falling back to Wikipedia for major US tickers...")
            try:
                wiki_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
                resp = requests.get(wiki_url, timeout=15)
                # Ensure we have valid HTML and it's not a generic error page
                if resp.status_code == HTTP_OK:
                    df_list = pd.read_html(io.StringIO(resp.text))
                    for df_wiki in df_list:
                        col = next(
                            (
                                c
                                for c in df_wiki.columns
                                if "Symbol" in str(c) or "Ticker" in str(c)
                            ),
                            None,
                        )
                        if col is not None:
                            all_tickers.extend(df_wiki[col].dropna().astype(str).tolist())
                            break
                else:
                    logger.error(f"Wikipedia request failed with status: {resp.status_code}")
            except Exception as e:
                logger.error(f"Failed to fetch from Wikipedia: {type(e).__name__}: {e}")

        # 重複削除とクリーンアップ
        valid_pattern = re.compile(r"^[A-Z.\-]+$")
        unique_tickers = sorted(
            list(set(t for t in all_tickers if t and valid_pattern.match(str(t))))
        )

        if unique_tickers:
            df_save = pd.DataFrame({"Ticker": unique_tickers})
            df_save.to_csv(cache_file, index=False)
            logger.info(f"Successfully discovered {len(unique_tickers)} US tickers.")
            return unique_tickers

        if cache_file.exists():
            return pd.read_csv(cache_file)["Ticker"].tolist()
        return []
