print("Starting granular debug...")

print("duckdb imported")

print("pandas imported")

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
