import os
import time
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from src.universe import UniverseManager

def test_nasdaq_and_ttl():
    um = UniverseManager(cache_dir="./data/universe_test")
    cache_file = Path("./data/universe_test/us_tickers_full.csv")
    
    # Cleanup previous test runs
    if cache_file.exists():
        os.remove(cache_file)

    print("--- Test 1: Initial Discovery ---")
    start_time = time.time()
    tickers = um.get_us_universe()
    elapsed = time.time() - start_time
    
    print(f"Discovered: {len(tickers)} tickers")
    print(f"Time taken: {elapsed:.2f}s")
    assert len(tickers) > 10000, f"Expected > 10000 tickers, got {len(tickers)}"
    assert cache_file.exists(), "Cache file should be created"

    print("\n--- Test 2: Cache Hit (Immediate) ---")
    start_time = time.item() if hasattr(time, 'item') else time.time() # Dummy check
    start_time = time.time()
    tickers_cached = um.get_us_universe()
    elapsed_cached = time.time() - start_time
    
    print(f"Discovered (from cache): {len(tickers_cached)} tickers")
    print(f"Time taken: {elapsed_cached:.5f}s")
    assert elapsed_cached < 0.1, "Cache hit should be near-instant"

    print("\n--- Test 3: Cache Invalidation (Forced mtime) ---")
    # Set mtime to 25 hours ago
    past_time = time.time() - (25 * 3600)
    os.utime(cache_file, (past_time, past_time))
    
    print("Mtime set to 25 hours ago. Triggering discovery...")
    start_time = time.time()
    tickers_stale = um.get_us_universe()
    elapsed_stale = time.time() - start_time
    
    print(f"Discovered (after reload): {len(tickers_stale)} tickers")
    print(f"Time taken: {elapsed_stale:.2f}s")
    assert elapsed_stale > 0.5, "Should have performed a network request"
    
    print("\n--- Summary ---")
    print("Status: ✅ SUCCESS")
    print(f"Final Count: {len(tickers_stale)} symbols found in US market.")

if __name__ == "__main__":
    test_nasdaq_and_ttl()
