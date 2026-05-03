"""
Daily Stock Price DB - Gold Standard Logic Assets
This file contains the core logic components refined during the hardening mission.
Intended for reuse in cross-system integrations (e.g., Intrinsic Value Engine).
"""

import pandas as pd
import numpy as np
from datetime import datetime

# --- Component 1: Precision Schema Enforcement ---
def enforce_high_precision_schema(df: pd.DataFrame, ticker: str, source: str) -> pd.DataFrame:
    """
    Enforces float32/int64 schema for financial auditability and overflow safety.
    """
    if df.empty:
        return pd.DataFrame()
    df = df.copy()
    if "Date" not in df.columns and df.index.name == "Date":
        df = df.reset_index()
    
    df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
    # Prices & Splits: float32 handles values up to 10^38 with sufficient decimals
    for col in ["Open", "High", "Low", "Close", "StockSplits"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype(np.float32)
            
    # Volume: int64 handles huge volumes (trillions of shares)
    if "Volume" in df.columns:
        df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").fillna(0).astype(np.int64)
    
    df["Ticker"] = str(ticker).upper()
    df["Source"] = str(source)
    df["LoadTimestamp"] = datetime.now()
    return df

# --- Component 2: Smart Deduplication SQL ---
def generate_smart_dedupe_sql(ticker: str, parquet_paths: list[str]) -> str:
    """
    Generates DuckDB SQL that prioritizes the latest sync data per date.
    """
    paths_list = [str(p).replace("\\", "/") for p in parquet_paths]
    return f"""
    SELECT * EXCLUDE (row_num)
    FROM (
        SELECT *,
               row_number() OVER (PARTITION BY Date ORDER BY LoadTimestamp DESC) as row_num
        FROM read_parquet({paths_list})
        WHERE Ticker = '{ticker}'
    )
    WHERE row_num = 1
    ORDER BY Date ASC
    """.strip()

# --- Component 3: Catalog Path Pruning ---
class CatalogPruner:
    """
    Logic for mapping Tickers to specific Parquet partitions using SQLite.
    """
    def __init__(self, sqlite_conn):
        self.conn = sqlite_conn
        
    def resolve_paths(self, ticker: str, data_type: str = "price"):
        res = self.conn.execute(
            "SELECT file_path FROM ticker_index WHERE ticker = ? AND data_type = ?",
            (ticker, data_type)
        ).fetchall()
        return [r[0] for r in res]
