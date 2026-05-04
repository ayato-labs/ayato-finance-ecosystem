import time
from datetime import date, timedelta
from pathlib import Path
from typing import ClassVar

from loguru import logger

from src.core.config import settings
from src.core.db import db_manager
from src.core.logging import track_performance
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
        try:
            self.client = EDINETClient()
            self.storage = EDINETStorage()
            self.parser = EDINETParser()
            self.mapper = EDINETMapper(str(self.storage.raw_db_path))
            self.ai_mapper = AIMapper()
            logger.info("EDINETSyncWorker initialized with 3-Layer Physical Separation (Raw/Norm).")
        except Exception as e:
            logger.error(f"Failed to initialize EDINETSyncWorker: {e}")
            raise

    @track_performance("ensure_ticker_master_edinet")
    def ensure_ticker_master(self, force_update: bool = False):
        """
        Ensures the EDINET ticker master table is populated.
        Downloads the CSV from EDINET if it's empty or force_update is True.
        """
        try:
            target_codes = self.mapper.get_all_target_edinet_codes()
            if not target_codes or force_update:
                logger.info("EDINET ticker master is empty or update requested. Syncing...")
                master_dir = settings.DATA_DIR / "master"
                csv_path = self.client.download_edinet_code_list(master_dir)
                self.mapper.load_csv(str(csv_path))
        except Exception as e:
            logger.error(f"Failed to auto-sync ticker master: {e}")
            if not self.mapper.get_all_target_edinet_codes():
                raise RuntimeError("Ticker master is empty and auto-sync failed.") from e

    @track_performance("sync_date_edinet")
    def sync_date(
        self,
        target_date: date,
        target_edinet_codes: set[str] | None = None,
        allowed_types: set[str] | None = None,
    ):
        """
        Syncs all relevant statutory documents for a specific date.
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

                if allowed_types and type_code not in allowed_types:
                    continue

                # 2. Target Filter (Only listed companies from CSV master)
                if target_edinet_codes and edinet_code not in target_edinet_codes:
                    continue

                # 3. Incremental Check: Skip if already exists in RAW
                if self.storage.is_document_exists(doc_id):
                    logger.info(f"[SKIP] Document {doc_id} already exists in RAW storage.")
                    continue

                filer = doc.get("filerName", "Unknown")
                desc = doc.get("docDescription", "No Desc")
                logger.info(f"[SYNC] Processing: {filer} ({desc}) doc_id={doc_id}")

                try:
                    # 1. Save metadata to RAW
                    self.storage.save_document(doc)

                    # 2. Download statutory CSV zip
                    zip_content = self.client.download_document_csv(doc_id)
                    if not zip_content:
                        continue

                    # 3. Extract and Parse CSVs
                    csv_files = self.client.extract_csv_from_zip(zip_content)
                    all_facts = []
                    for _filename, content in csv_files:
                        facts = self.parser.parse_financial_csv(content)
                        all_facts.extend(facts)

                    # 4. Save Raw Facts to RAW (Bronze)
                    if all_facts:
                        self.storage.save_facts(doc_id, all_facts)

                        # 5. Map and Save to NORM (Silver)
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

                time.sleep(1)

            logger.info(f"=== Sync Complete: {target_date}. Processed {processed_count} docs. ===")

        except Exception as e:
            logger.error(f"Critical error during sync for {target_date}: {e}", exc_info=True)
            raise

    @track_performance("map_and_save_facts_edinet")
    def _map_and_save_facts(self, doc: dict, raw_facts: list[dict]):
        """
        Uses AI Mapper to translate EDINET raw facts to standardized labels
        and saves them to the NORMALIZED database (Silver).
        """
        try:
            doc_id = doc["docID"]
            ticker = doc.get("secCode")
            if ticker:
                ticker = str(ticker)
                if len(ticker) == 5:
                    ticker = ticker[:4]

            submit_dt = doc.get("submitDateTime")
            submission_date = submit_dt.split(" ")[0] if submit_dt else None
            session_id = f"edinet-sync-{date.today()}"

            # Only sync if not already in J-Quants (Gold)
            if self._has_jquants_data(ticker, submission_date):
                logger.info(f"[MAP] Skipping AI mapping for {ticker} (exists in J-Quants Gold).")
                return

            # Unique tags for efficient mapping
            unique_tags = {}
            for f in raw_facts:
                tag = f["id"]
                if tag not in unique_tags:
                    unique_tags[tag] = f["name"]

            tags_to_map = [(tag, desc) for tag, desc in unique_tags.items()]
            logger.info(f"[MAP] Mapping {len(tags_to_map)} unique tags for {ticker}...")

            fiscal_year, fiscal_period = self._extract_fiscal_info(doc)
            mappings = self.ai_mapper.map_tags_bulk("EDINET", tags_to_map, session_id)
            tag_to_label = {m["source_tag"].split(":", 1)[1]: m["mapped_label"] for m in mappings}

            # 1. Pivot the raw facts into a single wide-format record for SILVER
            wide_record = {
                "DisclosedDate": submission_date,
                "LocalCode": ticker,
                "FiscalYear": str(fiscal_year) if fiscal_year else None,
                "FiscalPeriod": fiscal_period,
                "session_id": session_id,
                "accession_number": doc_id,
            }

            # 2. Map facts to columns using standard labels
            valid_labels = set(settings.JQUANTS_V2_LABELS) if market in ["EDINET", "JP_EDINET"] else set(settings.TARGET_LABELS)
            for f in raw_facts:
                label = tag_to_label.get(f["id"])
                if label and label != "Other" and label in valid_labels:
                    try:
                        wide_record[label] = float(f["value"])
                    except (ValueError, TypeError):
                        logger.warning(f"Failed to convert {label} value '{f['value']}' to float.")

            if len(wide_record) > 6:
                self.storage.save_normalized_facts([wide_record])
                logger.info(f"[MAP] Successfully saved Silver record for {ticker} to edinet_normalized.")
            else:
                logger.warning(f"[MAP] No facts mapped to standard labels for {ticker}.")
        except Exception as e:
            doc_id_label = doc_id if "doc_id" in locals() else "unknown"
            logger.error(f"[MAP] Failed to map facts for {doc_id_label}: {e}")
            raise

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
                res = conn.execute(
                    "SELECT count(*) FROM company_facts WHERE LocalCode = ? AND DisclosedDate = ?",
                    (ticker, submission_date),
                ).fetchone()
                return res[0] > 0 if res else False
        except Exception as e:
            logger.debug(f"Failed to check J-Quants DB: {e}")
            return False

    @track_performance("run_historical_backfill_edinet")
    def run_historical_backfill(self, years: int = 5, csv_path: str | None = None):
        """
        Performs a full historical backfill of statutory data in 2 phases:
        Phase 1: Latest 30 days - Priority Reports (Annual/Quarterly)
        Phase 2: Full Range - All Reports
        """
        try:
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
            logger.info("=== [Phase 1] Priority Sync: Annual/Quarterly Reports ===")
            priority_range = 30
            priority_types = {"120", "130"}
            for i in range(priority_range + 1):
                target_date = end_date - timedelta(days=i)
                self.sync_date(
                    target_date, target_edinet_codes=target_codes, allowed_types=priority_types
                )

            # PHASE 2: Deep Backfill (Full range, all relevant types)
            logger.info(
                f"=== [Phase 2] Historical Backfill: {actual_years} years ==="
            )
            delta = end_date - start_date
            for i in range(delta.days + 1):
                target_date = end_date - timedelta(days=i)
                self.sync_date(target_date, target_edinet_codes=target_codes)
                time.sleep(0.5)
        except Exception as e:
            logger.error(f"Historical backfill failed: {e}")
            raise

    @track_performance("run_incremental_sync_edinet")
    def run_incremental_sync(self, default_days: int = 30):
        """Syncs from the last stored date to today."""
        from src.core.master import master_manager
        job_id = master_manager.start_job("EDINET-Incremental-Sync", ["edinet_raw", "edinet_norm"])
        
        try:
            self.ensure_ticker_master(force_update=True)

            last_date = self.storage.get_last_sync_date()
            if not last_date:
                logger.warning(f"No previous sync data found. Defaulting to {default_days} days.")
                last_date = date.today() - timedelta(days=default_days)

            start_date = last_date
            end_date = date.today()

            delta = end_date - start_date
            logger.info(f"Incremental sync: {start_date} to {end_date} ({delta.days} days)")

            target_codes = set(self.mapper.get_all_target_edinet_codes())
            
            total_docs = 0
            for i in range(delta.days + 1):
                target_date = start_date + timedelta(days=i)
                logger.info(
                    f"--- [INC] Processing Date {i + 1}/{delta.days + 1}: {target_date} ---"
                )
                # Note: processed_count in sync_date is local, ideally we should return it
                self.sync_date(target_date, target_edinet_codes=target_codes)
            
            master_manager.end_job(job_id, status="COMPLETED")
        except Exception as e:
            logger.error(f"Incremental sync failed: {e}")
            master_manager.end_job(job_id, status="FAILED", error_message=str(e))
            raise

    @track_performance("run_backfill_edinet")
    def run_backfill(self, days: int = 7):
        """Backfill data for the last N days sequentially."""
        from src.core.master import master_manager
        job_id = master_manager.start_job("EDINET-Backfill", ["edinet_raw", "edinet_norm"])
        
        try:
            logger.info(f"Starting backfill for the last {days} days.")
            end_date = date.today()
            for i in range(days):
                target_date = end_date - timedelta(days=i)
                self.sync_date(target_date)
            master_manager.end_job(job_id, status="COMPLETED")
        except Exception as e:
            logger.error(f"Backfill failed: {e}")
            master_manager.end_job(job_id, status="FAILED", error_message=str(e))
            raise



if __name__ == "__main__":
    # Setup basic logging if run directly
    worker = EDINETSyncWorker()
    worker.run_incremental_sync()
