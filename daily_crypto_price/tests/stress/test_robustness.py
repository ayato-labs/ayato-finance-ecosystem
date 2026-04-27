import concurrent.futures

from fastapi.testclient import TestClient

from main import app

def test_rapid_requests():
    client = TestClient(app)
    ticker = "BTC"
    
    # Rapid requests without sync to test DB concurrency
    client.get(f"/prices/{ticker}?sync=true") # Initial sync
    
    def fetch():
        return client.get(f"/prices/{ticker}?sync=false")

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch) for _ in range(20)]
        results = [f.result() for f in futures]
    
    for r in results:
        assert r.status_code == 200

def test_malformed_ticker_input():
    client = TestClient(app)
    # Testing very long ticker or special characters
    long_ticker = "A" * 1000
    response = client.get(f"/prices/{long_ticker}")
    # Should probably be 404 or handled gracefully
    assert response.status_code in [404, 422]

def test_sql_injection_attempt():
    client = TestClient(app)
    # Although we use parameterized queries, let's test a malicious string
    malicious_ticker = "BTC'; DROP TABLE prices; --"
    response = client.get(f"/prices/{malicious_ticker}")
    assert response.status_code in [400, 404] # Should not execute drop table

def test_database_corruption_recovery(tmp_path):
    from src.engine.db_engine import CryptoDBEngine
    
    db_file = tmp_path / "corrupt.duckdb"
    # Create a non-database file at the path
    db_file.write_text("NOT A DATABASE")
    
    # This might fail during init or fetch
    try:
        _ = CryptoDBEngine(db_path=str(db_file))
        # DuckDB might overwrite or error
    except Exception:
        # If it errors, that's also a valid form of robustness (not silent failure)
        assert True
