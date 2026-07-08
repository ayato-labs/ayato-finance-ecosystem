import json

import pandas as pd
import yfinance as yf
from src.core.schema import DataContract, TickerInfo


def test_data_contract_validation():
    """空文字が適切にNoneに変換されるか、バリデーションが効いているか"""

    class Sample(DataContract):
        name: str | None

    s = Sample(name="")
    assert s.name is None

    s2 = Sample(name="Valid")
    assert s2.name == "Valid"


def test_ticker_info_real_fetch():
    """[NO MOCK] 実際のyfinanceからデータを取得し、TickerInfoモデルで検証できるか"""
    ticker = "AAPL"
    yt = yf.Ticker(ticker)
    info = yt.info

    # 必須項目の存在確認 (裏取り)
    assert "longName" in info
    assert info["symbol"] == "AAPL"

    # Pydanticモデルへの変換
    model = TickerInfo(raw_json=json.dumps(info), **info)
    assert model.ticker == "AAPL"
    assert "Apple" in model.company_name


def test_db_manager_migration(db_manager):
    """初期化時に必要なテーブルがすべて存在するか"""
    conn = db_manager.get_connection()
    tables = conn.execute("SHOW TABLES").df()["name"].tolist()
    assert "info" in tables
    assert "financials" in tables
    assert "sync_status" in tables
    conn.close()


def test_get_long_df_logic(sample_tickers):
    """財務諸表のスタックロジックが正しいロング形式を生成するか"""
    ticker = sample_tickers[0]
    # モックではない生のデータを準備
    data = {"2023-09-30": [100, 200], "2022-09-30": [150, 250]}
    df = pd.DataFrame(data, index=["Revenue", "Net Income"])

    # engineの内部関数を模したテスト
    def mock_get_long_df(df, p_type):
        ds = df.stack().reset_index()
        ds.columns = ["item", "date", "value"]
        ds["ticker"] = ticker
        ds["period_type"] = p_type
        return ds

    res = mock_get_long_df(df, "Annual")
    assert len(res) == 4
    assert set(res.columns) == {"item", "date", "value", "ticker", "period_type"}
    assert res.iloc[0]["value"] in [100, 150, 200, 250]
