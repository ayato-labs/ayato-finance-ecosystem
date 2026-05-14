import threading

from src.infra.db import db_manager


def test_db_manager_connection_sharing(tmp_path, monkeypatch):
    """
    Unit: Verify that the DB manager correctly shares the in-memory connection
    within the same process and handles concurrent access.
    """
    monkeypatch.setenv("MASTER_DB_PATH", ":memory:")

    def connect_work():
        with db_manager.connect_master() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER)")
            conn.execute("INSERT INTO test VALUES (1)")

    threads = [threading.Thread(target=connect_work) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # If no exception, lock coordination works within same process

    with db_manager.connect_master() as conn:
        count = conn.execute("SELECT count(*) FROM test").fetchone()[0]
        assert count == 5


def test_db_manager_physical_file(tmp_path, monkeypatch):
    """
    Unit: Verify DB manager with a physical file.
    """
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("MASTER_DB_PATH", str(db_file))
    monkeypatch.setenv("REGISTRY_DB_PATH", str(tmp_path / "reg.db"))
    monkeypatch.setenv("FACTS_DB_PATH", str(tmp_path / "facts.db"))
    monkeypatch.setenv("NARRATIVE_DB_PATH", str(tmp_path / "narr.db"))

    with db_manager.connect_master() as conn:
        conn.execute("CREATE TABLE test_phys (id INTEGER)")
        conn.execute("INSERT INTO test_phys VALUES (100)")

    assert db_file.exists()
