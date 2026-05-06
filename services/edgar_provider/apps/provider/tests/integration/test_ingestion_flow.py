from edgar_core.db import db_manager
from edgar_core.master_db import master_db
from edgar_provider\.engine import USEngine


def test_full_routing_integration():
    """
    Integration test:
    Verify that numerical facts land in facts_db and
    narratives land in narratives_db, both tracked by master_db.
    """
    engine = USEngine()
    session_id = "test-integration-123"

    # 1. Manually trigger a small ingestion or mock specific parts
    from edgar_core.contracts import USFactContract, USNarrativeContract, USFilingContract

    filing = USFilingContract(
        accession_number="TEST-ACCN-1",
        ticker="AAPL",
        cik="0000320193",
        form="10-K",
        filed_date="2024-01-01",
        session_id=session_id,
    )

    fact = USFactContract(
        accession_number="TEST-ACCN-1",
        fiscal_year=2023,
        fiscal_period="FY",
        label="Revenue",
        value=394000000.0,
        unit="USD",
        is_standardized=True,
    )

    narrative = USNarrativeContract(
        ticker="AAPL",
        cik="0000320193",
        accession_number="TEST-ACCN-1",
        form="10-K",
        filed_date="2024-01-01",
        section_name="Risk Factors",
        content_md_zstd=b"compressed-content",
        session_id=session_id,
    )

    # Act
    engine._save_facts([filing], [fact])
    engine._save_narrative(narrative)

    # Assert: Facts DB has the filing and the fact
    with db_manager.connect(engine.facts_db) as conn:
        f_count = conn.execute(
            "SELECT count(*) FROM filings WHERE ticker = 'AAPL'"
        ).fetchone()[0]
        assert f_count == 1
        
        c_count = conn.execute(
            "SELECT count(*) FROM company_facts WHERE accession_number = 'TEST-ACCN-1'"
        ).fetchone()[0]
        assert c_count == 1

    # Assert: Narratives DB has the narrative
    with db_manager.connect(engine.narratives_db) as conn:
        count = conn.execute(
            "SELECT count(*) FROM narratives WHERE ticker = 'AAPL'"
        ).fetchone()[0]
        assert count == 1

    # Assert: Master DB connection can see both via ATTACH and Star JOIN
    with master_db.get_connection_with_attachments(read_only=True) as conn:
        res = conn.execute("""
            SELECT f.label, n.section_name, fl.ticker
            FROM facts_db.company_facts f
            JOIN facts_db.filings fl ON f.accession_number = fl.accession_number
            JOIN narratives_db.narratives n ON f.accession_number = n.accession_number
            WHERE fl.ticker = 'AAPL'
        """).fetchone()
        assert res == ("Revenue", "Risk Factors", "AAPL")
