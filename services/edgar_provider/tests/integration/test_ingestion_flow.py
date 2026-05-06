from src.core.db import db_manager
from src.core.master_db import master_db
from src.engine import USEngine


def test_full_routing_integration():
    """
    Integration test:
    Verify that numerical facts land in facts_db and
    narratives land in narratives_db, both tracked by master_db.
    """
    engine = USEngine()
    session_id = "test-integration-123"

    # 1. Manually trigger a small ingestion or mock specific parts
    # For integration, we allowed mocking. Let's simulate a 'AAPL' landing.
    from src.core.contracts import USFactContract, USNarrativeContract

    fact = USFactContract(
        ticker="AAPL", cik="0000320193", accession_number="TEST-ACCN-1",
        form="10-K", filed_date="2024-01-01", fiscal_year=2023, fiscal_period="FY",
        label="Revenue", value=394000000.0, unit="USD", is_standardized=True,
        session_id=session_id
    )

    narrative = USNarrativeContract(
        ticker="AAPL", cik="0000320193", accession_number="TEST-ACCN-1",
        form="10-K", filed_date="2024-01-01", section_name="Risk Factors",
        content_md_zstd=b"compressed-content", session_id=session_id
    )

    # Act
    engine._save_facts([fact])
    engine._save_narrative(narrative)

    # Assert: Facts DB has the fact
    with db_manager.connect(engine.facts_db) as conn:
        count = conn.execute(
            "SELECT count(*) FROM company_facts WHERE ticker = 'AAPL'"
        ).fetchone()[0]
        assert count == 1

    # Assert: Narratives DB has the narrative
    with db_manager.connect(engine.narratives_db) as conn:
        count = conn.execute(
            "SELECT count(*) FROM narratives WHERE ticker = 'AAPL'"
        ).fetchone()[0]
        assert count == 1
    # Assert: Master DB connection can see both via ATTACH
    with master_db.get_connection_with_attachments(read_only=True) as conn:
        # Cross-db query simulation
        res = conn.execute("""
            SELECT f.label, n.section_name
            FROM facts_db.company_facts f
            JOIN narratives_db.narratives n ON f.accession_number = n.accession_number
            WHERE f.ticker = 'AAPL'
        """).fetchone()
        assert res == ("Revenue", "Risk Factors")
