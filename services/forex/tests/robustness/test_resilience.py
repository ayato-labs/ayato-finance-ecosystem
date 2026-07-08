import threading
from datetime import datetime

import pandas as pd
from src.engine import ForexEngine
from src.fetchers.forex_fetcher import ForexFetcher


def test_forex_fetcher_api_failure(mocker):
    """APIがエラーを返した場合の耐性"""
    fetcher = ForexFetcher()
    # yfinanceが例外を投げるケース
    mocker.patch("yfinance.Ticker.history", side_effect=Exception("API limit reached"))

    df = fetcher.fetch("JPY", datetime(2024, 1, 1))
    assert df.empty


def test_forex_engine_corrupted_parquet(temp_forex_dir):
    """Parquetファイルが破損している場合の挙動"""
    engine = ForexEngine(temp_forex_dir)
    file_path = f"{temp_forex_dir}/JPY.parquet"

    # 不正なデータを書き込む
    with open(file_path, "w") as f:
        f.write("not a parquet file")

    # DuckDB経由でエラーを吐かずに空を返すか(実装によるが、現在はログを吐いて[]を返すはず)
    rates = engine.get_rates("JPY")
    assert rates == []


def test_forex_engine_concurrent_writes(temp_forex_dir):
    """並列書き込みへの耐性 (簡易版)"""
    engine = ForexEngine(temp_forex_dir)

    def writer(i):
        df = pd.DataFrame(
            {
                "Date": [pd.Timestamp("2024-01-01") + pd.Timedelta(days=i)],
                "Symbol": ["JPY"],
                "Rate": [0.007],
                "LoadTimestamp": [pd.Timestamp.now()],
            }
        )
        engine.save_data("JPY", df)

    num_threads = 10
    threads = [threading.Thread(target=writer, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    rates = engine.get_rates("JPY")
    assert len(rates) == num_threads
