from pathlib import Path
import uuid
import duckdb
from loguru import logger

from src.datalake.service.ensemble_parser import ensemble_parse
from src.datalake.shared.infra.manifest import (
    init_manifest,
    get_document_status,
    update_document_status,
)
from src.datalake.shared.infra.trace import trace_step

DB_PATH = Path("data/edinet_facts.duckdb")


@trace_step("parse_document")
def step_parse(xbrl_path: Path, csv_path: Path, doc_id: str, run_id: str = None):
    return ensemble_parse(xbrl_path, csv_path, doc_id)


@trace_step("store_eav")
def step_store_eav(doc_id: str, results: dict, run_id: str = None):
    con = duckdb.connect(str(DB_PATH))

    # Ensure table exists
    con.execute("""
        CREATE TABLE IF NOT EXISTS company_facts (
            doc_id VARCHAR,
            item_name VARCHAR,
            item_value VARCHAR,
            PRIMARY KEY (doc_id, item_name)
        )
    """)

    # Prepare data
    data_to_insert = []
    for k, v in results.items():
        data_to_insert.append((doc_id, k, str(v)))

    # Insert
    con.executemany(
        """
        INSERT OR REPLACE INTO company_facts (doc_id, item_name, item_value)
        VALUES (?, ?, ?)
    """,
        data_to_insert,
    )

    con.close()
    return len(results)


@trace_step("convert_wide")
def step_convert_wide(run_id: str = None):
    con = duckdb.connect(str(DB_PATH))

    # Check tables
    tables = [t[0] for t in con.execute("PRAGMA show_tables").fetchall()]
    if "company_facts" not in tables or "edinet_codes" not in tables:
        con.close()
        raise Exception(f"Required tables missing. Found: {tables}")

    sql = """
    CREATE OR REPLACE TABLE financial_statements AS
    WITH pivoted AS (
        PIVOT (
            SELECT 
                doc_id,
                CASE 
                    WHEN item_name IN ('net_sales_cons', 'net_sales_non_cons') THEN 'net_sales'
                    WHEN item_name IN ('total_assets_cons', 'total_assets_non_cons') THEN 'total_assets'
                    WHEN item_name IN ('total_liabilities_cons', 'total_liabilities_non_cons') THEN 'total_liabilities'
                    WHEN item_name IN ('net_income_cons', 'net_income_non_cons') THEN 'net_income'
                END AS std_name,
                CAST(item_value AS DOUBLE) AS val
            FROM company_facts
            WHERE std_name IS NOT NULL
              AND item_name LIKE '%_non_cons'
        )
        ON std_name IN ('net_sales', 'total_assets', 'total_liabilities', 'net_income')
        USING FIRST(val)
    ),
    edinet_mapping AS (
        SELECT DISTINCT
            doc_id,
            item_value AS edinet_code
        FROM company_facts
        WHERE item_name = 'raw_mcp_EntityEDINETCodeDEI'
    )
    SELECT 
        p.doc_id,
        m.security_code,
        m.company_name AS master_company_name,
        m.corporate_number,
        p.net_sales,
        p.total_assets,
        p.total_liabilities,
        p.net_income
    FROM pivoted p
    LEFT JOIN edinet_mapping em ON p.doc_id = em.doc_id
    LEFT JOIN edinet_codes m ON em.edinet_code = m.edinet_code
    """

    con.execute(sql)
    count = con.execute("SELECT COUNT(*) FROM financial_statements").fetchone()[0]
    con.close()
    return count


def run_pipeline(doc_ids: list):
    """Run the full pipeline for a list of documents."""
    run_id = str(uuid.uuid4())
    logger.info(f"=== Starting Pipeline Run: {run_id} ===")

    init_manifest()

    for doc_id in doc_ids:
        logger.info(f"Processing document: {doc_id}")

        # Check status
        status = get_document_status(doc_id)
        if status == "stored":
            logger.info(f"Skipping {doc_id} - already processed (Status: {status})")
            continue

        xbrl_path = Path(f"data/{doc_id}_xbrl.zip")
        csv_path = Path(f"data/{doc_id}_csv.zip")

        if not xbrl_path.exists():
            logger.warning(f"Files not found for {doc_id}. Skipping.")
            continue

        try:
            # Step 1: Parse
            results = step_parse(xbrl_path, csv_path, doc_id, run_id=run_id)

            # Fallback for EDINET Code
            if "raw_mcp_EntityEDINETCodeDEI" not in results:
                doc_to_edinet = {"S100XT8B": "G01853", "S100XRSA": "E04730"}
                if doc_id in doc_to_edinet:
                    results["raw_mcp_EntityEDINETCodeDEI"] = doc_to_edinet[doc_id]

            # Step 2: Store EAV
            items_stored = step_store_eav(doc_id, results, run_id=run_id)
            logger.info(f"Stored {items_stored} items for {doc_id}")

            # Step 3: Convert Wide (Run after each document to keep it simple for now)
            rows_converted = step_convert_wide(run_id=run_id)
            logger.info(f"Total rows in financial_statements: {rows_converted}")

            # Update status
            update_document_status(doc_id, "stored")
            logger.info(f"Successfully completed {doc_id}")

        except Exception as e:
            logger.error(f"Failed to process {doc_id}: {e}", exc_info=True)
            update_document_status(doc_id, "failed")

    logger.info(f"=== Completed Pipeline Run: {run_id} ===")
