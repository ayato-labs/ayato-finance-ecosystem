import datetime

import edinet_tools
from loguru import logger

from src.datalake.engine import JPEDINETEngine
from src.datalake.shared.infra.db import db_manager


def test_backfill_single():
    engine = JPEDINETEngine()
    doc_id = "S100LBVH"  # Nitori

    logger.info(f"Targeting backfill for {doc_id}...")

    # We need to get the Document object from edinet_tools
    # Nitori filed on 2021-05-14
    docs = edinet_tools.documents(date=datetime.date(2021, 5, 14))
    target_doc = next((d for d in docs if d._data.get("docID") == doc_id), None)

    if not target_doc:
        logger.error("Could not find document object via API")
        return

    result, status = engine.ingestor._process_single_doc(target_doc, "9843", "debug-backfill")
    if result:
        logger.info(f"Successfully processed {doc_id}. Found {len(result['facts'])} facts.")
        with db_manager.connect_master() as conn:
            engine.ingestor._flush_results_to_db(conn, [result])
        logger.info("Flushed to DB.")
    else:
        logger.error(f"Processing failed: {status}")


if __name__ == "__main__":
    test_backfill_single()
