import datetime
import json
import os
import time
from typing import Any

import edinet_tools
from edinet_tools.document import Document
from loguru import logger

from src.shared.infra.config import settings
from src.shared.infra.db import db_manager


class DataRepository:
    """
    Data Access Layer (Repository Pattern).
    Separated from ingestion logic to allow lightweight API access.
    """

    @staticmethod
    def get_documents_with_cache(target_date: datetime.date) -> list[Document]:
        """Fetches document list with local JSON caching (24h validity)."""
        cache_dir = settings.DATA_DIR / "manifests"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{target_date.isoformat()}.json"

        if cache_file.exists():
            mtime = os.getmtime(cache_file)
            if (time.time() - mtime) < 86400:
                try:
                    logger.debug(f"Cache HIT for documents on {target_date}")
                    with open(cache_file, encoding="utf-8") as f:
                        cached_data = json.load(f)
                    return [Document(data) for data in cached_data]
                except Exception as e:
                    logger.warning(f"Failed to load cache {cache_file}: {e}")

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
    def search_filings(
        edinet_code: str | None = None,
        ticker: str | None = None,
        company_name: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        logger.debug(
            f"Searching filings: edinet_code={edinet_code}, ticker={ticker}, "
            f"company_name={company_name}, start={start_date}, end={end_date}"
        )
        with db_manager.connect_master(read_only=True) as conn:
            query = "SELECT * FROM registry_db.filings WHERE 1=1"
            params = []
            if edinet_code:
                query += " AND edinet_code = ?"
                params.append(edinet_code)
            if ticker:
                query += " AND sec_code LIKE ?"
                params.append(f"%{ticker}%")
            if company_name:
                query += " AND filer_name LIKE ?"
                params.append(f"%{company_name}%")
            if start_date:
                query += " AND submit_datetime >= ?"
                params.append(start_date)
            if end_date:
                query += " AND submit_datetime <= ?"
                params.append(end_date)

            query += " ORDER BY submit_datetime DESC LIMIT 1000"
            logger.debug(f"Executing query: {query} with params: {params}")

            try:
                rel = conn.execute(query, params)
                columns = [desc[0] for desc in rel.description]
                rows = rel.fetchall()
                logger.debug(f"Query executed successfully, fetched {len(rows)} rows")

                results = []
                for row in rows:
                    d = {}
                    for col, val in zip(columns, row, strict=False):
                        if isinstance(val, (datetime.datetime, datetime.date)):
                            serialized_val = val.isoformat()
                        elif isinstance(val, str):
                            serialized_val = "".join(
                                c for c in val if c.isprintable() or c in "\t\n\r"
                            )
                        else:
                            serialized_val = val
                        d[col] = serialized_val
                    results.append(d)
                return results
            except Exception as e:
                logger.error(f"Search filings failed: {e}", exc_info=True)
                raise
