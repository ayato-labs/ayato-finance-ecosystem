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
                    with open(cache_file, "r", encoding="utf-8") as f:
                        cached_data = json.load(f)
                    from edinet_tools.document import Document

                    return [Document(data) for data in cached_data]
                except Exception as e:
                    logger.warning(f"Failed to load cache {cache_file}: {e}")

        time.sleep(0.2)
        docs = edinet_tools.documents(date=target_date)

        if docs is not None:
            try:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(
                        [doc._data for doc in docs], f, ensure_ascii=False, indent=2
                    )
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
