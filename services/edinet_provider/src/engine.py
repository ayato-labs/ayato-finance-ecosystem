import pandas as pd
import zstandard as zstd
from loguru import logger
import edinet_tools
from src.core.config import settings
from src.core.db import db_manager

class JPEDINETEngine:
    def __init__(self):
        if not settings.EDINET_API_KEY:
            logger.warning("EDINET_API_KEY is not set. API calls will fail.")
        
        # Configure the global client in edinet_tools
        edinet_tools.configure(api_key=settings.EDINET_API_KEY)
        
        self.db_path = settings.DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self.compressor = zstd.ZstdCompressor(level=settings.ZSTD_COMPRESSION_LEVEL)

    def _init_db(self):
        from src.core.migrations import MigrationManager
        MigrationManager.apply_migrations(self.db_path)

    def sync_company(self, ticker: str, days: int = 30, session_id: str = "manual"):
        """Sync specific company's latest filings."""
        logger.info(f"Syncing JP Company {ticker} (Last {days} days)...")
        try:
            # edinet-tools provides module-level 'entity' function
            entity = edinet_tools.entity(ticker)
            docs = entity.documents(days=days)
            
            for doc in docs:
                # 1. Metadata Ingestion
                self._ingest_metadata(doc, ticker, session_id)
                
                # 2. Qualitative (Narratives) from XBRL
                self._ingest_narratives(doc, ticker, session_id)
                
                # 3. Quantitative (Facts) from CSV
                self._ingest_facts_from_csv(doc, ticker, session_id)

        except Exception as e:
            logger.error(f"Failed to sync {ticker}: {e}")

    def _ingest_metadata(self, doc, ticker, session_id):
        data = doc._data
        with db_manager.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR IGNORE INTO filings 
                (doc_id, edinet_code, sec_code, filer_name, doc_description, 
                 submit_datetime, form_code, doc_type_code, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                data.get("docID"), data.get("edinetCode"), ticker, 
                data.get("filerName"), data.get("docDescription"), 
                data.get("submitDateTime"), data.get("formCode"), 
                data.get("docTypeCode"), session_id
            ])

    def _ingest_narratives(self, doc, ticker, session_id):
        """Extract narratives using edinet-tools parse()."""
        try:
            data = doc._data
            # Only parse if it's a Securities Report (120) or similar
            # formCode for Annual Report is typically '030000'
            if data.get("formCode") not in ["030000", "043000"]: 
                return

            report = doc.parse()
            # edinet-tools report object might have different structure.
            # Let's use a more cautious extraction.
            sections = {
                "事業等のリスク": getattr(getattr(report, "business", None), "risks", None),
                "経営方針、経営環境及び対処すべき課題": getattr(getattr(report, "business", None), "policy_environment_issue_etc", None),
                "経営者による財政状態、経営成績及びキャッシュ・フローの状況の分析": getattr(getattr(report, "business", None), "analysis_of_financial_results", None)
            }
            
            filed_date = pd.to_datetime(data.get("submitDateTime")).date()

            for name, content in sections.items():
                if content and len(content) > 100:
                    compressed = self.compressor.compress(content.encode('utf-8'))
                    with db_manager.connect(self.db_path) as conn:
                        conn.execute("""
                            INSERT OR REPLACE INTO narratives 
                            (doc_id, ticker, section_name, content_md_zstd, filed_date, session_id)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, [
                            data.get("docID"), ticker, name, compressed, 
                            filed_date, session_id
                        ])
            logger.info(f"Narratives ingested for {ticker} (DocID: {data.get('docID')})")
        except Exception as e:
            logger.warning(f"Narrative extraction failed for {doc.doc_id}: {e}")

    def _ingest_facts_from_csv(self, doc, ticker, session_id):
        """Download and parse official CSV for numerical facts."""
        try:
            from src.core.csv_parser import get_csv_from_edinet, parse_edinet_csv
            data = doc._data
            if data.get("csvFlag") != "1":
                return

            content = get_csv_from_edinet(data.get("docID"), settings.EDINET_API_KEY)
            if not content:
                return

            csv_data = parse_edinet_csv(content)
            filed_date = pd.to_datetime(data.get("submitDateTime")).date()
            
            for file_name, df in csv_data.items():
                if df is None or df.empty:
                    continue
                
                # Based on debug_csv_raw.py:
                # Column 0: 隕∫ｴID (Element ID)
                # Column 1: 隕∫ｴ蜷 (Element Name / Item Name)
                # Column 8: 蛟､ (Value)
                # Column 7: 蜊倅ｽ (Unit) - sometimes
                
                cols = df.columns.tolist()
                if len(cols) < 9:
                    continue

                item_name_col = cols[1]
                unit_col = cols[7]
                value_col = cols[8]

                for _, row in df.iterrows():
                    item_name = row[item_name_col]
                    item_value = row[value_col]
                    unit = row[unit_col]
                    
                    if pd.notna(item_value):
                        try:
                            # Handle string numbers
                            str_val = str(item_value).replace(',', '')
                            val_float = float(str_val)
                            
                            with db_manager.connect(self.db_path) as conn:
                                conn.execute("""
                                    INSERT OR REPLACE INTO company_facts 
                                    (doc_id, ticker, item_name, item_value, unit, context_id, 
                                     filed_date, fiscal_year, fiscal_period, session_id)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, [
                                    data.get("docID"), ticker, str(item_name), val_float, 
                                    str(unit), str(file_name), filed_date, 
                                    filed_date.year, "FY", session_id
                                ])
                        except (ValueError, TypeError):
                            continue
            logger.info(f"Facts (CSV) ingested for {ticker} (DocID: {data.get('docID')})")
        except Exception as e:
            logger.warning(f"CSV fact ingestion failed for {doc.doc_id}: {e}")
