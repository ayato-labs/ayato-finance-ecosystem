import asyncio
from pathlib import Path
import uuid
import duckdb
import zstandard as zstd
from loguru import logger

from src.datalake.service.ensemble_parser import ensemble_parse
from src.datalake.shared.infra.manifest import (
    get_document_status,
    update_document_status,
    init_manifest,
)
from src.datalake.shared.infra.trace import init_logging
from src.datalake.service.csv_parser import get_document_from_edinet
from src.datalake.shared.infra.config import settings

DB_PATH = Path("data/datalake/edinet_facts.duckdb")


async def downloader_worker(doc_ids: list, parse_queue: asyncio.Queue, run_id: str):
    """
    Worker 1: Parallel I/O (simulated for now with local files).
    Checks manifest and pushes valid doc_ids to parse_queue.
    """
    logger.info(f"[Downloader] Starting with {len(doc_ids)} documents")

    for doc_id in doc_ids:
        # Manifest filtering
        status = get_document_status(doc_id)
        if status in ["stored", "PARSED", "CONVERTED"]:
            logger.info(f"[Downloader] Skipping {doc_id} - already processed.")
            continue

        # Check if file exists, if not download from EDINET API
        xbrl_path = Path(f"data/{doc_id}_xbrl.zip")
        csv_path = Path(f"data/{doc_id}_csv.zip")

        if not xbrl_path.exists():
            logger.info(f"[Downloader] Downloading XBRL for {doc_id} from API...")
            try:
                content = get_document_from_edinet(doc_id, settings.EDINET_API_KEY, doc_type=1)
                with open(xbrl_path, "wb") as f:
                    f.write(content)
                logger.info(f"[Downloader] Successfully downloaded {doc_id}_xbrl.zip")
                update_document_status(doc_id, "FETCHED")
            except Exception as e:
                logger.error(f"[Downloader] Failed to download {doc_id}: {e}")
                continue

        logger.info(f"[Downloader] Queuing {doc_id} for parsing")
        await parse_queue.put((doc_id, xbrl_path, csv_path))

    # Signal end of queue
    await parse_queue.put(None)
    logger.info("[Downloader] Finished")


async def parser_worker(
    parse_queue: asyncio.Queue,
    facts_queue: asyncio.Queue,
    narratives_queue: asyncio.Queue,
    uploader_queue: asyncio.Queue,
    run_id: str,
):
    """
    Worker 2: CPU Heavy Parsing.
    Reads from parse_queue, runs ensemble_parse, and pushes to appropriate queues.
    """
    logger.info("[Parser] Starting")

    while True:
        item = await parse_queue.get()
        if item is None:
            # Propagate end signal
            await facts_queue.put(None)
            await narratives_queue.put(None)
            await uploader_queue.put(None)
            parse_queue.task_done()
            break

        doc_id, xbrl_path, csv_path = item
        logger.info(f"[Parser] Processing {doc_id}")

        try:
            results = ensemble_parse(xbrl_path, csv_path, doc_id)

            # Put 3 brains data into facts_queue
            await facts_queue.put(
                (
                    doc_id,
                    {
                        "mcp": results.get("mcp", {}),
                        "tools": results.get("tools", {}),
                        "csv": results.get("csv", {}),
                        "narratives": results.get("narratives", {}),
                    },
                )
            )

            # Put narratives into narratives_queue
            await narratives_queue.put((doc_id, results.get("narratives", {})))

            # Queue for Google Drive upload
            await uploader_queue.put((doc_id, xbrl_path, csv_path))

            logger.info(f"[Parser] Completed {doc_id}")
        except Exception as e:
            logger.error(f"[Parser] Failed for {doc_id}: {e}", exc_info=True)
            # Clean up temporary ZIPs if parsing failed, to prevent storage leaks
            try:
                if xbrl_path.exists():
                    xbrl_path.unlink()
                if csv_path.exists():
                    csv_path.unlink()
                logger.info(f"[Parser] Cleaned up ZIP files for failed doc {doc_id}")
            except Exception as cleanup_err:
                logger.warning(f"[Parser] Failed to clean up ZIPs for {doc_id}: {cleanup_err}")

        parse_queue.task_done()

    logger.info("[Parser] Finished")


async def writer_worker(facts_queue: asyncio.Queue, run_id: str):
    """
    Worker 3: Serialized I/O (DuckDB).
    Reads from facts_queue and writes to DB one by one.
    """
    logger.info("[Writer] Starting")

    # Connect to 3 separate databases + narratives DB
    con_mcp = duckdb.connect("data/datalake/facts_mcp.duckdb")
    con_tools = duckdb.connect("data/datalake/facts_tools.duckdb")
    con_csv = duckdb.connect("data/datalake/facts_csv.duckdb")
    con_narr = duckdb.connect("data/datalake/edinet_narratives.duckdb")

    def init_table(conn):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS company_facts (
                doc_id VARCHAR,
                item_name VARCHAR,
                item_value VARCHAR,
                PRIMARY KEY (doc_id, item_name)
            )
        """)

    def init_narrative_table(conn):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS narratives (
                doc_id VARCHAR,
                section_name VARCHAR,
                content_md BLOB,
                session_id VARCHAR,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (doc_id, section_name)
            )
        """)

    init_table(con_mcp)
    init_table(con_tools)
    init_table(con_csv)
    init_narrative_table(con_narr)

    while True:
        item = await facts_queue.get()
        if item is None:
            facts_queue.task_done()
            break

        doc_id, brains_data = item
        logger.info(f"[Writer] Storing {doc_id} to separate DBs")

        try:
            # 1. Store edinet-mcp facts
            data_mcp = [
                (doc_id, k, str(v)) for k, v in brains_data.get("mcp", {}).items() if v is not None
            ]
            if data_mcp:
                con_mcp.executemany(
                    """
                    INSERT OR REPLACE INTO company_facts (doc_id, item_name, item_value)
                    VALUES (?, ?, ?)
                """,
                    data_mcp,
                )

            # 2. Store edinet-tools facts
            data_tools = [
                (doc_id, k, str(v))
                for k, v in brains_data.get("tools", {}).items()
                if v is not None
            ]
            if data_tools:
                con_tools.executemany(
                    """
                    INSERT OR REPLACE INTO company_facts (doc_id, item_name, item_value)
                    VALUES (?, ?, ?)
                """,
                    data_tools,
                )

            # 3. Store CSV facts
            data_csv = [
                (doc_id, k, str(v)) for k, v in brains_data.get("csv", {}).items() if v is not None
            ]
            if data_csv:
                con_csv.executemany(
                    """
                    INSERT OR REPLACE INTO company_facts (doc_id, item_name, item_value)
                    VALUES (?, ?, ?)
                """,
                    data_csv,
                )

            # 4. Store narratives (zstd compressed)
            data_narr = brains_data.get("narratives", {})
            if data_narr:
                cctx = zstd.ZstdCompressor(level=settings.ZSTD_COMPRESSION_LEVEL)
                narrative_batch = []
                for k, v in data_narr.items():
                    compressed = cctx.compress(str(v).encode("utf-8"))
                    narrative_batch.append((doc_id, k, compressed, run_id))

                con_narr.executemany(
                    """
                    INSERT OR REPLACE INTO narratives (doc_id, section_name, content_md, session_id)
                    VALUES (?, ?, ?, ?)
                """,
                    narrative_batch,
                )

            # Update manifest
            update_document_status(doc_id, "PARSED")
            logger.info(f"[Writer] Successfully stored {doc_id} in all DBs")
        except Exception as e:
            logger.error(f"[Writer] Failed for {doc_id}: {e}")
            update_document_status(doc_id, "failed")

        facts_queue.task_done()

    # Close connections
    con_mcp.close()
    con_tools.close()
    con_csv.close()
    con_narr.close()
    logger.info("[Writer] Finished")


async def file_writer_worker(narratives_queue: asyncio.Queue, run_id: str):
    """
    Worker 4: File I/O (Text Data).
    Reads from narratives_queue and writes to files.
    """
    logger.info("[File Writer] Starting")

    narratives_dir = Path("data/narratives")
    narratives_dir.mkdir(parents=True, exist_ok=True)

    while True:
        item = await narratives_queue.get()
        if item is None:
            narratives_queue.task_done()
            break

        doc_id, narratives = item
        if not narratives:
            narratives_queue.task_done()
            continue

        logger.info(f"[File Writer] Storing narratives for {doc_id}")

        doc_dir = narratives_dir / doc_id
        doc_dir.mkdir(parents=True, exist_ok=True)

        for k, v in narratives.items():
            file_path = doc_dir / f"{k}.md"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(str(v))

        narratives_queue.task_done()

    logger.info("[File Writer] Finished")


async def uploader_worker(uploader_queue: asyncio.Queue, run_id: str):
    """
    Worker 5: File I/O (Google Drive upload/move).
    Reads from uploader_queue and moves ZIP files to Google Drive folder.
    """
    logger.info("[Uploader] Starting")

    drive_dir = settings.GOOGLE_DRIVE_DIR
    drive_dir.mkdir(parents=True, exist_ok=True)

    while True:
        item = await uploader_queue.get()
        if item is None:
            uploader_queue.task_done()
            break

        doc_id, xbrl_path, csv_path = item
        logger.info(f"[Uploader] Moving ZIPs for {doc_id} to Google Drive")

        try:
            import shutil

            if xbrl_path.exists():
                shutil.move(str(xbrl_path), str(drive_dir / xbrl_path.name))
            if csv_path.exists():
                shutil.move(str(csv_path), str(drive_dir / csv_path.name))
            logger.info(f"[Uploader] Successfully moved ZIPs for {doc_id}")
        except Exception as e:
            logger.error(f"[Uploader] Failed to move ZIPs for {doc_id}: {e}")

        uploader_queue.task_done()

    logger.info("[Uploader] Finished")


async def run_async_pipeline(doc_ids: list):
    """Main entry point for async pipeline."""
    init_logging()
    run_id = str(uuid.uuid4())
    logger.info(f"=== Starting Async Pipeline Run: {run_id} ===")

    init_manifest()

    parse_queue = asyncio.Queue(maxsize=5)
    facts_queue = asyncio.Queue(maxsize=5)
    narratives_queue = asyncio.Queue(maxsize=5)
    uploader_queue = asyncio.Queue(maxsize=5)

    # Run all workers concurrently
    await asyncio.gather(
        downloader_worker(doc_ids, parse_queue, run_id),
        parser_worker(parse_queue, facts_queue, narratives_queue, uploader_queue, run_id),
        writer_worker(facts_queue, run_id),
        file_writer_worker(narratives_queue, run_id),
        uploader_worker(uploader_queue, run_id),
    )

    logger.info(f"=== Completed Async Pipeline Run: {run_id} ===")
