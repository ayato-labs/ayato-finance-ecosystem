import time
from datetime import date, timedelta
from pathlib import Path
from typing import ClassVar

from loguru import logger

from src.core.config import settings
from src.core.db import db_manager
from src.mappers.ai_mapper import AIMapper

from .client import EDINETClient
from .mapping import EDINETMapper
from .parser import EDINETParser
from .storage import EDINETStorage


class EDINETSyncWorker:
    """
    Coordinates the end-to-end sync of EDINET statutory filings.
    Designed for maximum traceability and auditability.
    """

    # docTypeCode: 120 (Annual), 130 (Quarterly), 140 (Semi-annual), 150 (Extraordinary)
    RELEVANT_DOC_TYPES: ClassVar[set[str]] = {"120", "130", "140", "150"}

    def __init__(self):
        self.client = EDINETClient()
        self.storage = EDINETStorage()
        self.parser = EDINETParser()
        self.mapper = EDINETMapper(str(self.storage.db_path))
        self.ai_mapper = AIMapper()
        logger.info("EDINETSyncWorker initialized with Mapping Support and AI Mapper.")

    def ensure_ticker_master(self, force_update: bool = False):
        """
        Ensures the EDINET ticker master table is populated.
        Downloads the CSV from EDINET if it's empty or force_update is True.
        """
        target_codes = self.mapper.get_all_target_edinet_codes()
        if not target_codes or force_update:
            logger.info("EDINET ticker master is empty or update requested. Syncing from EDINET...")
            master_dir = Path(self.storage.db_path).parent / "master"
            try:
                csv_path = self.client.download_edinet_code_list(master_dir)
                self.mapper.load_csv(str(csv_path))
            except Exception as e:
                logger.error(f"Failed to auto-sync ticker master: {e}")
                if not target_codes:
                    raise RuntimeError("Ticker master is empty and auto-sync failed.") from e

    def sync_date(
        self,
        target_date: date,
        target_edinet_codes: set[str] | None = None,
        allowed_types: set[str] | None = None,
    ):
        """
        Syncs all relevant statutory documents for a specific date.
        If target_edinet_codes is provided, only processes documents from those submitters.
        If allowed_types is provided, only processes documents of those types.
        """
        logger.info(f"=== Starting EDINET Sync: {target_date} ===")

        try:
            doc_list_resp = self.client.get_document_list(target_date)
            results = doc_list_resp.get("results", [])

            if not results:
                logger.info(f"No documents found for {target_date}.")
                return

            processed_count = 0
            for doc in results:
                doc_id = doc.get("docID")
                type_code = doc.get("docTypeCode")
                edinet_code = doc.get("edinetCode")

                # 1. Type Filter (Only Financial Statements)
                if type_code not in self.RELEVANT_DOC_TYPES:
                    continue

                # 1.b. Priority Filter (e.g. only 120/130 if specified)
                if allowed_types and type_code not in allowed_types:
                    continue

                # 2. Target Filter (Only listed companies from CSV master)
                if target_edinet_codes and edinet_code not in target_edinet_codes:
                    continue

                # 3. Incremental Check: Skip if already exists
                if self.storage.is_document_exists(doc_id):
                    logger.info(f"[SKIP] Document {doc_id} already exists in storage.")
                    continue

                filer = doc.get("filerName", "Unknown")
                desc = doc.get("docDescription", "No Desc")
                logger.info(f"[SYNC] Processing: {filer} ({desc}) doc_id={doc_id}")

                try:
                    # 1. Save metadata
                    self.storage.save_document(doc)

                    # 2. Download statutory CSV zip
                    logger.debug(f"[SYNC] Downloading ZIP for {doc_id}...")
                    zip_content = self.client.download_document_csv(doc_id)
                    if not zip_content:
                        logger.warning(f"[SYNC] No content returned for {doc_id}")
                        continue

                    # 3. Extract and Parse CSVs
                    logger.debug(f"[SYNC] Extracting CSVs from ZIP {doc_id}...")
                    csv_files = self.client.extract_csv_from_zip(zip_content)
                    all_facts = []
                    for _filename, content in csv_files:
                        facts = self.parser.parse_financial_csv(content)
                        all_facts.extend(facts)

                    # 4. Save Raw Facts for Audit
                    if all_facts:
                        logger.info(
                            f"[SYNC] Saving {len(all_facts)} raw facts for audit trail "
                            f"(doc_id={doc_id})."
                        )
                        self.storage.save_facts(doc_id, all_facts)

                        # 5. Map to Standardized Facts
                        try:
                            self._map_and_save_facts(doc, all_facts)
                        except Exception as e:
                            logger.error(f"[MAP] Failed to map and save facts for {doc_id}: {e}")
                    else:
                        logger.warning(f"No numeric facts extracted from {doc_id}")

                    processed_count += 1

                except Exception as e:
                    logger.exception(f"Failed to process document {doc_id}: {e}")
                    continue

                # Rate limiting: Be respectful to EDINET servers (1s per doc download)
                time.sleep(1)

            logger.info(f"=== Sync Complete: {target_date}. Processed {processed_count} docs. ===")

        except Exception as e:
            logger.error(f"Critical error during sync for {target_date}: {e}", exc_info=True)
            raise

    def _map_and_save_facts(self, doc: dict, raw_facts: list[dict]):
        """
        Uses AI Mapper to translate EDINET raw facts to standardized labels
        and saves them to the wide-format company_facts table.
        """
        doc_id = doc["docID"]
        ticker = doc.get("secCode")
        if ticker:
            ticker = str(ticker)
            ticker_len_full = 5
            if len(ticker) == ticker_len_full and ticker.endswith("0"):
                ticker = ticker[:4]
            elif len(ticker) == ticker_len_full:
                ticker = ticker[:4]

        submission_date = doc.get("submissionPeriod")
        session_id = f"edinet-sync-{date.today()}"

        if self._has_jquants_data(ticker, submission_date):
            logger.info(f"[MAP] Skipping AI mapping for {ticker} as J-Quants data already exists.")
            return

        # Unique tags for efficient mapping
        unique_tags = {}
        for f in raw_facts:
            tag = f["id"]
            if tag not in unique_tags:
                unique_tags[tag] = f["name"]

        tags_to_map = [(tag, desc) for tag, desc in unique_tags.items()]
        logger.info(f"[MAP] Mapping {len(tags_to_map)} unique tags for {ticker}...")

        try:
            fiscal_year, fiscal_period = self._extract_fiscal_info(doc)
            mappings = self.ai_mapper.map_tags_bulk("EDINET", tags_to_map, session_id)
            tag_to_label = {m["source_tag"].split(":", 1)[1]: m["mapped_label"] for m in mappings}

            # 1. Pivot the raw facts into a single wide-format record
            # We initialize with basic metadata
            wide_record = {
                "DisclosedDate": submission_date,
                "LocalCode": ticker,
                "FiscalYear": str(fiscal_year) if fiscal_year else None,
                "FiscalPeriod": fiscal_period,
                "session_id": session_id,
                "accession_number": doc_id,
            }

            # 2. Map facts to columns
            for f in raw_facts:
                label = tag_to_label.get(f["id"])
                # If the AI mapped this tag to a standard J-Quants label, put it in that column
                if label and label != "Other":
                    # We store the latest value if there are multiple (EDINET has duplicates)
                    wide_record[label] = str(f["value"])
                    # Also keep track of the original tag and label for traceability
                    # or just rely on the wide-format for standard queries.
                    wide_record["tag"] = f["id"]
                    wide_record["label"] = label

            if len(wide_record) > 6:  # More than just the metadata
                self.storage.save_normalized_facts([wide_record])
                logger.info(f"[MAP] Successfully saved wide-format record for {ticker}.")
            else:
                logger.warning(f"[MAP] No facts mapped to standard labels for {ticker}.")

        except Exception as e:
            logger.error(f"[MAP] Failed to map facts for {doc_id}: {e}")

    def _extract_fiscal_info(self, doc: dict) -> tuple[int | None, str | None]:
        """
        Extracts fiscal year and period from document metadata.
        """
        period_end = doc.get("periodEnd")
        doc_desc = doc.get("docDescription", "")

        fiscal_year = None
        if period_end:
            try:
                # Typically YYYY-MM-DD
                fiscal_year = int(period_end.split("-")[0])
            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse fiscal year from periodEnd '{period_end}': {e}")

        fiscal_period = None
        if "有価証券報告書" in doc_desc:
            fiscal_period = "FY"
        elif "四半期報告書" in doc_desc:
            if "第1四半期" in doc_desc:
                fiscal_period = "Q1"
            elif "第2四半期" in doc_desc:
                fiscal_period = "Q2"
            elif "第3四半期" in doc_desc:
                fiscal_period = "Q3"
            else:
                fiscal_period = "Q"

        return fiscal_year, fiscal_period

    def _has_jquants_data(self, ticker: str, submission_date: str) -> bool:
        """Checks if J-Quants DB already has entries for this ticker and date."""
        if not settings.DB_PATH_JP.exists():
            return False
        try:
            with db_manager.connect(settings.DB_PATH_JP, read_only=True) as conn:
                # Use disclosed_date to match submissionPeriod
                res = conn.execute(
                    "SELECT count(*) FROM company_facts WHERE code = ? AND disclosed_date = ?",
                    (ticker, submission_date),
                ).fetchone()
                return res[0] > 0 if res else False
        except Exception as e:
            logger.debug(f"Failed to check J-Quants DB: {e}")
            return False

    def run_historical_backfill(self, years: int = 5, csv_path: str | None = None):
        """
        Performs a full historical backfill of statutory data in 2 phases:
        Phase 1: Latest 30 days - Priority Reports (Annual/Quarterly)
        Phase 2: Full Range - All Reports
        """
        # Always update master at the start of backfill
        if csv_path:
            self.mapper.load_csv(csv_path)
        else:
            self.ensure_ticker_master(force_update=True)

        target_codes = set(self.mapper.get_all_target_edinet_codes())
        if not target_codes:
            logger.error("No target EDINET codes found in mapping. Cannot perform backfill.")
            return

        actual_years = min(years, 5)
        end_date = date.today()
        start_date = end_date - timedelta(days=actual_years * 365)

        # PHASE 1: Priority Lane (Latest 30 days, 120/130 only)
        logger.info("=== [Phase 1] Priority Sync: Latest 30 days (Annual/Quarterly Reports) ===")
        priority_range = 30
        priority_types = {"120", "130"}
        for i in range(priority_range + 1):
            target_date = end_date - timedelta(days=i)
            self.sync_date(
                target_date, target_edinet_codes=target_codes, allowed_types=priority_types
            )

        # PHASE 2: Deep Backfill (Full range, all relevant types)
        logger.info(
            f"=== [Phase 2] Historical Backfill: {actual_years} years (All relevant reports) ==="
        )
        delta = end_date - start_date
        for i in range(delta.days + 1):
            target_date = end_date - timedelta(days=i)
            # Process everything that wasn't skipped or handled in Phase 1
            self.sync_date(target_date, target_edinet_codes=target_codes)

            # Additional safety sleep between days
            time.sleep(0.5)

    def run_incremental_sync(self, default_days: int = 30):
        """Syncs from the last stored date to today."""
        # Always update master at the start of sync
        self.ensure_ticker_master(force_update=True)

        last_date = self.storage.get_last_sync_date()
        if not last_date:
            logger.warning(f"No previous sync data found. Defaulting to last {default_days} days.")
            last_date = date.today() - timedelta(days=default_days)

        start_date = last_date
        end_date = date.today()

        delta = end_date - start_date
        logger.info(f"Incremental sync: {start_date} to {end_date} ({delta.days} days)")

        target_codes = set(self.mapper.get_all_target_edinet_codes())
        if not target_codes:
            logger.warning(
                "Ticker master is empty. Syncing all statutory documents without filtering."
            )
        else:
            logger.info(f"Filtering sync for {len(target_codes)} listed companies.")

        for i in range(delta.days + 1):
            target_date = start_date + timedelta(days=i)
            logger.info(f"--- [INC] Processing Date {i + 1}/{delta.days + 1}: {target_date} ---")
            self.sync_date(target_date, target_edinet_codes=target_codes)

    def run_backfill(self, days: int = 7):
        """Backfill data for the last N days sequentially."""
        logger.info(f"Starting backfill for the last {days} days.")
        end_date = date.today()
        for i in range(days):
            target_date = end_date - timedelta(days=i)
            self.sync_date(target_date)


if __name__ == "__main__":
    # Setup basic logging if run directly
    worker = EDINETSyncWorker()
    worker.run_incremental_sync()
