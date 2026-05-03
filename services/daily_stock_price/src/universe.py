import io
import re
import time
from pathlib import Path

import pandas as pd
import requests
from loguru import logger


class UniverseManager:
    def __init__(self, cache_dir: str = "./data/universe"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

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
        NasdaqTraderから米国株全銘柄リストを取得。24時間キャッシュ。
        """
        cache_file = self.cache_dir / "us_tickers_full.csv"
        if self._is_cache_fresh(cache_file):
            df = pd.read_csv(cache_file)
            return df["Ticker"].tolist()

        logger.info("Fetching full US ticker list from NasdaqTrader...")
        urls = [
            "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt",
            "https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt"
        ]
        headers = {"User-Agent": "Mozilla/5.0"}
        all_tickers = []

        try:
            for url in urls:
                resp = requests.get(url, headers=headers, timeout=15)
                resp.raise_for_status()

                # 文字列として読み込み、最後のフッター (File Creation Time等) を除去
                lines = resp.text.splitlines()
                clean_lines = [
                    line for line in lines
                    if "|" in line and not line.startswith("File Creation Time")
                ]

                df = pd.read_csv(io.StringIO("\n".join(clean_lines)), sep="|")
                # カラム名がSymbolになっているものを抽出
                col_name = "Symbol" if "Symbol" in df.columns else "NASDAQ Symbol"
                if col_name in df.columns:
                    all_tickers.extend(df[col_name].dropna().astype(str).tolist())

            # 重複削除とクリーンアップ (TEST銘柄等を除去)
            # 2026-04-17: BRK.B や BRK-A などの記号も許可するように正規表現でフィルタリング
            valid_pattern = re.compile(r"^[A-Z.\-]+$")
            unique_tickers = sorted(
                list(set(t for t in all_tickers if t and valid_pattern.match(str(t))))
            )

            # キャッシュ保存
            df_save = pd.DataFrame({"Ticker": unique_tickers})
            df_save.to_csv(cache_file, index=False)
            logger.info(f"Successfully discovered {len(unique_tickers)} US tickers.")
            return unique_tickers
        except Exception as e:
            logger.error(f"Failed to fetch US tickers from NasdaqTrader: {e}")
            # もし古いキャッシュがあればそれを返す (安全のため)
            if cache_file.exists():
                return pd.read_csv(cache_file)["Ticker"].tolist()
            return []
