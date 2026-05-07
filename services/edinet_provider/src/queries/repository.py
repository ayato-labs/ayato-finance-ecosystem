import datetime
import json
import os
import time

import edinet_tools
from loguru import logger

from src.infra.config import settings
from src.infra.db import db_manager


class DataRepository:
    """
    Data Access Layer (Repository Pattern).
    Separated from ingestion logic to allow lightweight API access.
    """

    @staticmethod
    def get_documents_with_cache(target_date: datetime.date):
        """Fetches document list with local JSON caching (24h validity)."""
        cache_dir = settings.DATA_DIR / "manifests"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{target_date.isoformat()}.json"

        if cache_file.exists():
            mtime = os.path.getmtime(cache_file)
            if (time.time() - mtime) < 86400:
                try:
                    logger.debug(f"Cache HIT for documents on {target_date}")
                    with open(cache_file, "r", encoding="utf-8") as f:
                        cached_data = json.load(f)
                    from edinet_tools.document import Document

                    return [Document(data) for data in cached_data]
                except Exception as e:
                    logger.warning(f"Failed to load cache {cache_file}: {e}")
                    # Fallback to API if cache load fails

        logger.debug(f"Cache MISS for documents on {target_date}. Fetching from EDINET...")
        try:
            time.sleep(0.2)
            docs = edinet_tools.documents(date=target_date)
            logger.info(
                f"Retrieved {len(docs) if docs else 0} documents from API for {target_date}"
            )
        except Exception as e:
            logger.error(f"EDINET API failure for date {target_date}: {e}")
            raise

        if docs is not None:
            try:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump([doc._data for doc in docs], f, ensure_ascii=False, indent=2)
                logger.debug(f"Documents for {target_date} cached to {cache_file}")
            except Exception as e:
                logger.warning(f"Failed to save cache {cache_file}: {e}")

        return docs or []

    @staticmethod
    def query_existing_filings():
        with db_manager.connect_master(read_only=True) as conn:
            try:
                return {
                    row[0]
                    for row in conn.execute("SELECT doc_id FROM registry_db.filings").fetchall()
                }
            except Exception as e:
                logger.error(f"Failed to query existing filings: {e}", exc_info=True)
                return set()
