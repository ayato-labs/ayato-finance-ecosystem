import logging
from datetime import datetime

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# 分割保存とクエリ時の最新抽出のためのスキーマ定義
COLUMNS = [
    "Date",
    "Ticker",
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
    "StockSplits",
    "Source",
    "LoadTimestamp",
]


def enforce_schema(df: pd.DataFrame, ticker: str, source: str) -> pd.DataFrame:
    """
    DataFrameのデータ型とカラムを統一し、LoadTimestampを付与する。
    """
    if df.empty:
        logger.warning(f"Empty DataFrame received for {ticker} from {source}")
        return pd.DataFrame(columns=COLUMNS)

    logger.info(f"Enforcing schema for {ticker} (Source: {source}, Rows: {len(df)})")

    # インデックスがDateの場合のリセット
    if "Date" not in df.columns and df.index.name == "Date":
        df = df.reset_index()
    elif "date" in df.columns:
        df = df.rename(columns={"date": "Date"})

    # 一旦コピーを作成して作業（破壊的変更を避ける）
    df = df.copy()

    # 欠損カラムの補完
    for col in COLUMNS:
        if col not in df.columns:
            if col == "Volume":
                df[col] = 0
            else:
                df[col] = np.nan

    df["Ticker"] = ticker
    df["Source"] = source
    df["LoadTimestamp"] = datetime.now()

    df = df[COLUMNS].copy()

    # 型変換（ストレージ節約と整合性）
    # 日付から時刻情報を排除（Date32最適化）
    df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
    df["LoadTimestamp"] = pd.to_datetime(df["LoadTimestamp"])

    # 価格データと分割比率は float32 を採用し、精度とオーバーフロー耐性を確保
    for col in ["Open", "High", "Low", "Close", "StockSplits"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(np.float32)

    # 出来高は int64 を採用し、巨大な出来高（21億超）にも対応可能とする
    df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").fillna(0).astype(np.int64)

    # 銘柄名とソース名はカテゴリ型に変更（Parquet Dictionary Encodingを強制）
    df["Ticker"] = df["Ticker"].astype("category")
    df["Source"] = df["Source"].astype("category")

    return df



