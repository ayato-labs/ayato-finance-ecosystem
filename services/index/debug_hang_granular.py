import sys
print("Starting granular debug...")
import duckdb
print("duckdb imported")
import pandas as pd
print("pandas imported")
from pathlib import Path
print("pathlib imported")
from src.engine import IndexEngine
print("IndexEngine class imported")
engine = IndexEngine()
print("IndexEngine instance created")
from src.fetchers.yf_fetcher import YFinanceFetcher
print("YFinanceFetcher class imported")
fetcher = YFinanceFetcher()
print("YFinanceFetcher instance created")
print("Done granular debug")
