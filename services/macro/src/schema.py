import logging
from datetime import datetime

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# マクロデータ用の基本スキーマ
COLUMNS = [
    "Date",
    "Symbol",
    "Value",
    "Source",
    "LoadTimestamp",
]


def enforce_schema(df: pd.DataFrame, symbol: str, source: str) -> pd.DataFrame:
    """
    DataFrameのデータ型とカラムをマクロデータ用に統一し、LoadTimestampを付与する。
    """
    if df.empty:
        logger.warning(f"Empty DataFrame received for {symbol} from {source}")
        return pd.DataFrame(columns=COLUMNS)

    # FREDなどのレスポンスがSeriesの場合、DataFrameに変換
    if isinstance(df, pd.Series):
        df = df.to_frame(name="Value")

    # インデックスがDateの場合のリセット
    if "Date" not in df.columns:
        df = df.reset_index()
        df = df.rename(columns={df.columns[0]: "Date", df.columns[1]: "Value"})

    df = df.copy()

    # 必要なカラムの補完と選択
    df["Symbol"] = symbol
    df["Source"] = source
    df["LoadTimestamp"] = datetime.now()

    # カラム名の正規化 (大文字小文字対策)
    df.columns = [c.capitalize() if c.lower() == "date" else c for c in df.columns]

    # 型変換
    df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
    df["LoadTimestamp"] = pd.to_datetime(df["LoadTimestamp"])
    df["Value"] = pd.to_numeric(df["Value"], errors="coerce").astype(np.float64)

    # 重複排除の準備として必要なカラムのみ抽出
    df = df[COLUMNS].copy()

    return df
