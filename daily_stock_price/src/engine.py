import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import pandas as pd

from .fetchers.base import BaseFetcher
from .logger import SyncLogger
from .catalog import CatalogManager

logger = logging.getLogger(__name__)


class MarketDataEngine:
    def __init__(
        self,
        fetcher: BaseFetcher,
        base_dir: str = "./data/market_data",
        log_dir: str = None,
    ):
        self.fetcher = fetcher
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # Derive log_dir from base_dir if not provided (keeping it inside the same root)
        if log_dir is None:
            self.log_dir = self.base_dir.parent / "logs"
        else:
            self.log_dir = Path(log_dir)

        self.sync_logger = SyncLogger(log_dir=str(self.log_dir))
        self.catalog = CatalogManager(db_path=self.base_dir.parent / "catalog.sqlite")

        logger.info(
            f"Initialized MarketDataEngine with base_dir: {self.base_dir} "
            f"using fetcher: {fetcher.source_name}"
        )

    def get_max_date(self, ticker: str) -> datetime:
        """
        全パーティションから特定のティッカーの最新日付を取得。
        """
        try:
            db = duckdb.connect()
            # カタログから対象パスを取得
            paths = self.catalog.get_paths(ticker, data_type="price")
            if not paths:
                return datetime(2000, 1, 1)

            # 特定のファイルリストのみを走査
            res = db.query(
                f"SELECT MAX(Date) FROM read_parquet({paths}) WHERE Ticker = '{ticker}'"
            ).fetchone()
            if res and res[0]:
                max_date = pd.to_datetime(res[0])
                logger.info(f"Max date found for {ticker}: {max_date}")
                return max_date
        except Exception as e:
            logger.info(f"No existing data or query failed for {ticker}: {e}")

        return datetime(2000, 1, 1)

    def sync_ticker(self, ticker: str, lookback_days: int = None):
        """
        差分更新 + 3日間上書きロジック。
        lookback_days が指定された場合は、DBの状態に関わらずその日数分を遡る。
        """
        if lookback_days:
            fetch_start = datetime.now() - timedelta(days=lookback_days)
        else:
            max_date = self.get_max_date(ticker)
            fetch_start = max_date - timedelta(days=3)

        if fetch_start < datetime(2000, 1, 1):
            fetch_start = datetime(2000, 1, 1)

        print(f"Syncing {ticker}: fetch starting from {fetch_start.date()}")
        fetch_end = datetime.now()

        try:
            # 1. 価格データの取得
            df_price = self.fetcher.fetch(ticker, fetch_start)
            if not df_price.empty:
                self.save_parquet(df_price)

            status = "SUCCESS"
            count = len(df_price)
            msg = f"Synced {count} prices."

            self.sync_logger.log_event(
                ticker, fetch_start, fetch_end, count, status, self.fetcher.source_name, msg
            )
            print(msg)

        except Exception as e:
            self.sync_logger.log_event(
                ticker, fetch_start, fetch_end, 0, "ERROR", self.fetcher.source_name, str(e)
            )
            logger.error(f"Sync failed for {ticker}: {e}")



    def sync_tickers(
        self,
        tickers: list[str],
        max_workers: int = 3,
        lookback_days: int = None,
        batch_size: int = 50,
    ):
        """
        大量銘柄を並列・一括ダウンロードで同期し、全ての試行をログに記録する。
        """
        total = len(tickers)
        processed_count = 0

        print(
            f"Starting bulk sync for {total} tickers with {max_workers} workers (Batch Size: {batch_size})..."
        )

        # 銘柄をチャンクに分割
        chunks = [tickers[i : i + batch_size] for i in range(0, len(tickers), batch_size)]

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_chunk = {}
            for chunk in chunks:
                if lookback_days:
                    fetch_start = datetime.now() - timedelta(days=lookback_days)
                else:
                    fetch_start = datetime.now() - timedelta(days=3)

                if fetch_start < datetime(2000, 1, 1):
                    fetch_start = datetime(2000, 1, 1)

                if hasattr(self.fetcher, "fetch_batch"):
                    future_to_chunk[
                        executor.submit(self.fetcher.fetch_batch, chunk, fetch_start)
                    ] = (chunk, fetch_start)
                else:
                    # Fallback
                    for t in chunk:
                        future_to_chunk[executor.submit(self.fetcher.fetch, t, fetch_start)] = (
                            [t],
                            fetch_start,
                        )

            for _i, future in enumerate(as_completed(future_to_chunk)):
                chunk, fetch_start = future_to_chunk[future]
                fetch_end = datetime.now()
                events = []

                try:
                    df = future.result()
                    # 取得された銘柄とその件数を把握
                    fetched_counts = {}
                    if not df.empty:
                        self.save_parquet(df)
                        fetched_counts = df.groupby("Ticker").size().to_dict()

                    # チャンク内の全銘柄に対してステータスを判定してログを準備
                    for t in chunk:
                        count = fetched_counts.get(t, 0)
                        status = "SUCCESS" if count > 0 else "EMPTY"
                        msg = f"Batch fetch result: {count} rows"
                        events.append(
                            {
                                "Ticker": t,
                                "PeriodStart": pd.to_datetime(fetch_start),
                                "PeriodEnd": pd.to_datetime(fetch_end),
                                "RecordsFetched": count,
                                "Status": status,
                                "Message": msg,
                                "Fetcher": self.fetcher.source_name,
                            }
                        )

                    print(f"  [BATCH DONE] Chunk of {len(chunk)} tickers processed.")
                except Exception as e:
                    logger.error(f"Failed to sync chunk {chunk[:3]}: {e}")
                    for t in chunk:
                        events.append(
                            {
                                "Ticker": t,
                                "PeriodStart": pd.to_datetime(fetch_start),
                                "PeriodEnd": pd.to_datetime(fetch_end),
                                "RecordsFetched": 0,
                                "Status": "ERROR",
                                "Message": str(e),
                                "Fetcher": self.fetcher.source_name,
                            }
                        )

                # まとめてログを永続化
                self.sync_logger.log_events(events)
                processed_count += len(chunk)
                print(f"Progress: {processed_count}/{total} tickers processed.")
                time.sleep(random.uniform(1.0, 3.0))

        print("Bulk sync completed. Trayceability logs updated in ./data/logs/")

    def save_parquet(self, df: pd.DataFrame):
        """
        データを期間(年・月)ごとにパーティショニングして保存。
        全銘柄を同じファイルに収めることで圧縮率を極限化する。
        """
        if df.empty:
            return

        # 年と月を抽出してグループ化
        df_working = df.copy()
        df_working["_pyear"] = df_working["Date"].dt.year
        df_working["_pmonth"] = df_working["Date"].dt.month

        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        for (year, month), group in df_working.groupby(["_pyear", "_pmonth"]):
            year_path = self.base_dir / f"year={year}"
            month_path = year_path / f"month={month:02d}"
            month_path.mkdir(parents=True, exist_ok=True)

            filename = f"batch_{ts_str}.parquet"
            # パーティション用の作業カラムを削除して保存
            save_df = group.drop(columns=["_pyear", "_pmonth"])

            save_df.to_parquet(
                month_path / filename,
                engine="pyarrow",
                compression="zstd",
                compression_level=12,  # 高圧縮レベル
                index=False,
                row_group_size=100_000,  # 大きめのRow Groupで圧縮効率を向上
            )
            # カタログ登録
            tickers = save_df["Ticker"].unique().tolist()
            mappings = [(t, str(month_path / filename), "price") for t in tickers]
            self.catalog.register_many(mappings)

            logger.info(f"Saved partition {year}/{month:02d} to {month_path / filename}")

    def get_synced_view(self, ticker: str) -> str:
        """
        最新の LoadTimestamp を持つレコードのみを抽出するクエリ。
        枝刈り (Pruning) を適用済み。
        """
        paths = self.catalog.get_paths(ticker, data_type="price")
        if not paths:
            return None

        sql = f"""
        SELECT * EXCLUDE (row_num)
        FROM (
            SELECT *,
                   row_number() OVER (PARTITION BY Date ORDER BY LoadTimestamp DESC) as row_num
            FROM read_parquet({paths})
            WHERE Ticker = '{ticker}'
        )
        WHERE row_num = 1
        ORDER BY Date ASC
        """
        return sql
