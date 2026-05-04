import duckdb
import pytest

from src.reconciler import Reconciler


@pytest.fixture
def mock_dbs(tmp_path):
    jp_db = tmp_path / "jp_lake.duckdb"
    us_db = tmp_path / "us_lake.duckdb"
    master_db = tmp_path / "master.sqlite"

    # Initialize DuckDBs with tables
    for db in [jp_db, us_db]:
        with duckdb.connect(str(db)) as conn:
            conn.execute(
                """
                CREATE TABLE filings (
                    accession_number VARCHAR PRIMARY KEY, ticker VARCHAR, cik VARCHAR,
                    form VARCHAR, filing_date DATE, sections JSON, metadata JSON,
                    updated_at TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE structured_data (
                    accession_number VARCHAR PRIMARY KEY, ticker VARCHAR,
                    structured_facts JSON, updated_at TIMESTAMP
                )
                """
            )

    return {"jp": str(jp_db), "us": str(us_db), "master": str(master_db)}


def test_reconciler_delta_detection(mock_dbs):
    # Setup state:
    # JP: 2 filings, 1 structured (1 pending)
    # US: 1 filing, 0 structured (1 pending)

    with duckdb.connect(mock_dbs["jp"]) as conn:
        conn.execute(
            """
            INSERT INTO filings VALUES (
                'JP-PENDING', '7203', 'E02144', '120', '2026-05-01', '{}', '{}', CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO filings VALUES (
                'JP-DONE', '9984', 'E02777', '120', '2026-05-01', '{}', '{}', CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "INSERT INTO structured_data VALUES ('JP-DONE', '9984', '{}', CURRENT_TIMESTAMP)"
        )

    with duckdb.connect(mock_dbs["us"]) as conn:
        conn.execute(
            """
            INSERT INTO filings VALUES (
                'US-PENDING', 'AAPL', '320193', '10-Q', '2026-05-01', '{}', '{}', CURRENT_TIMESTAMP
            )
            """
        )

    # Instantiate reconciler with mock paths
    reconciler = Reconciler()
    # 手動でパスを上書き（テスト用にDI可能にするのが理想だが、現状は属性を書き換える）
    reconciler.storage_jp.db_path = mock_dbs["jp"]
    reconciler.storage_us.db_path = mock_dbs["us"]
    reconciler.queue.db_path = mock_dbs["master"]
    reconciler.queue._init_db()

    # Run
    reconciler.run()

    # Verify SQLite
    stats = reconciler.queue.get_stats()
    # JP-PENDING と US-PENDING の2つが登録されているはず
    assert stats["PENDING"] == 2

    # 重複登録されないことも確認
    reconciler.run()
    assert reconciler.queue.get_stats()["PENDING"] == 2
