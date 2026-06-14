from datetime import datetime, timedelta

from dotenv import load_dotenv

from src.fetchers.fred_fetcher import FredFetcher

load_dotenv()


def test_fred_fetcher_real_unrate():
    """失業率 (UNRATE) を実際に取得してスキーマ整合性を確認"""
    fetcher = FredFetcher()
    # 直近3ヶ月分
    start_date = datetime.now() - timedelta(days=90)
    df = fetcher.fetch("UNRATE", start_date)

    assert not df.empty
    assert "Date" in df.columns
    assert "Value" in df.columns
    assert "Symbol" in df.columns
    assert (df["Symbol"] == "UNRATE").all()


def test_fred_fetcher_invalid_symbol():
    """存在しないシンボルでの挙動"""
    fetcher = FredFetcher()
    df = fetcher.fetch("INVALID_SYMBOL_99999", datetime.now())
    assert df.empty


def test_fred_fetcher_no_api_key():
    """APIキーがない場合の挙動"""
    fetcher = FredFetcher(api_key="INVALID_KEY")
    df = fetcher.fetch("UNRATE", datetime.now())
    assert df.empty
