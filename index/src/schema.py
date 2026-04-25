import logging
from datetime import datetime
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# 指数データ用の基本スキーマ
COLUMNS = [
    "Date",
    "Ticker",
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
    "Source",
    "LoadTimestamp",
]

def enforce_schema(df: pd.DataFrame, ticker: str, source: str) -> pd.DataFrame:
    """
    DataFrameのデータ型とカラムを指数データ用に統一し、LoadTimestampを付与する。
    """
    if df.empty:
        logger.warning(f"Empty DataFrame received for {ticker} from {source}")
        return pd.DataFrame(columns=COLUMNS)

    # インデックスがDateの場合のリセット
    if "Date" not in df.columns and df.index.name == "Date":
        df = df.reset_index()
    elif "date" in df.columns:
        df = df.rename(columns={"date": "Date"})

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

    # 必要なカラムのみ抽出
    df = df[COLUMNS].copy()

    # 型変換
    df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
    df["LoadTimestamp"] = pd.to_datetime(df["LoadTimestamp"])

    for col in ["Open", "High", "Low", "Close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(np.float32)

    df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").fillna(0).astype(np.int64)
    df["Ticker"] = df["Ticker"].astype("category")
    df["Source"] = df["Source"].astype("category")

    return df
