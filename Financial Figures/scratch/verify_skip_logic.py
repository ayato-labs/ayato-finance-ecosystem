import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from src.core.audit_manager import audit_manager


def test_skip_logic():
    market = "US"
    symbol = "TESTSKIP"

    # 1. Clear existing progress for test symbol
    with audit_manager._lock:
        with audit_manager._get_conn() as conn:
            conn.execute("DELETE FROM sync_progress WHERE market=? AND symbol=?", [market, symbol])

    # 2. Verify it's not in synced list
    synced = audit_manager.get_synced_symbols(market)
    assert symbol not in synced
    print(f"Verified: {symbol} not in synced list initially.")

    # 3. Log as skipped
    audit_manager.log_ticker_sync(market, symbol, 0, "SKIPPED_NOT_FOUND")
    print(f"Logged {symbol} as SKIPPED_NOT_FOUND.")

    # 4. Verify it's NOW in synced list
    synced = audit_manager.get_synced_symbols(market)
    assert symbol in synced
    print(f"Verified: {symbol} IS in synced list after skip logging.")

    # 5. Verify status 'ERROR' is NOT in synced list
    err_symbol = "TESTERROR"
    audit_manager.log_ticker_sync(market, err_symbol, 0, "ERROR: connection failed")
    synced = audit_manager.get_synced_symbols(market)
    assert err_symbol not in synced
    print(f"Verified: {err_symbol} is NOT in synced list after error logging.")


if __name__ == "__main__":
    test_skip_logic()
    print("All skip logic tests passed!")
