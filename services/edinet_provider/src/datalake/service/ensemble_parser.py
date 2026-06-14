import zipfile
import re
from pathlib import Path
from typing import Dict, Any
from loguru import logger

# Import parsers
from edinet_tools.parsers.securities import parse_securities_report
from src.datalake.service.markdown_converter import clean_html_to_markdown


class MockDocument:
    def __init__(self, zip_path: Path, doc_id: str):
        self.zip_path = zip_path
        self.doc_type_code = "120"  # Default to Securities Report
        self.doc_id = doc_id

    def fetch(self) -> bytes:
        with open(self.zip_path, "rb") as f:
            return f.read()


def parse_with_edinet_mcp(zip_path: Path, doc_id: str) -> Dict[str, Any]:
    """Brain 1: edinet-mcp (Bypassing categorization to salvage raw facts)"""
    import edinet_mcp
    import edinet_mcp.parser
    logger.info(f"[Ensemble] Running edinet-mcp (salvage mode) on {zip_path}")
    extract_dir = zip_path.parent / f"{doc_id}_extracted"

    import shutil

    try:
        # Extract if not exists
        if not extract_dir.exists():
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)

        parser = edinet_mcp.parser.XBRLParser()
        results = {}

        # Filter to likely instance documents as done in edinet-mcp
        xbrl_files = list(extract_dir.rglob("*.xbrl")) + list(extract_dir.rglob("*.xml"))
        xbrl_files = [
            f
            for f in xbrl_files
            if "manifest" not in f.name.lower()
            and "linkbase" not in f.name.lower()
            and "schema" not in f.name.lower()
        ]

        mcp_to_standard_mapping = {
            "OperatingRevenueFND": "net_sales",
            "NetSales": "net_sales",
            "NetSalesSummaryOfBusinessResults": "net_sales",
            "OperatingRevenue": "net_sales",
            "OperatingIncome": "operating_income",
            "OrdinaryIncome": "ordinary_income",
            "ProfitLoss": "net_income",
            "Assets": "total_assets",
            "TotalAssetsSummaryOfBusinessResults": "total_assets",
            "Liabilities": "total_liabilities",
            "NetAssets": "net_assets",
            "NetAssetsSummaryOfBusinessResults": "net_assets",
            "InterestExpense": "interest_expense",
            "InterestExpenses": "interest_expense",
            "InterestExpensesNOE": "interest_expense",
            "NetCashProvidedByUsedInOperatingActivities": "operating_cash_flow",
            "NetCashProvidedByUsedInOperatingActivitiesSummaryOfBusinessResults": "operating_cash_flow",
            "CurrentAssets": "current_assets",
            "CashAndDeposits": "cash_and_deposits",
            "CurrentLiabilities": "current_liabilities",
        }

        total_facts = 0
        for xbrl_file in xbrl_files:
            try:
                # Call the internal method directly to get all facts before categorization
                facts = parser._extract_xbrl_facts(xbrl_file)
            except Exception as e:
                logger.warning(f"[Ensemble] edinet-mcp facts extraction failed for {xbrl_file}: {e}")
                continue

            # Skipped debugging dump to optimize performance

            if facts:
                total_facts += len(facts)
                for fact in facts:
                    elem = fact.get("element")
                    val = fact.get("value")
                    context = fact.get("context", "")
                    if elem and val is not None:
                        # Prefix to identify source and avoid collisions
                        results[f"raw_mcp_{elem}"] = val

                        # Apply mapping for missing critical fields
                        if elem in mcp_to_standard_mapping and "CurrentYear" in context:
                            standard_key = mcp_to_standard_mapping[elem]
                            suffix = "_non_cons" if "NonConsolidated" in context else "_cons"
                            results[f"{standard_key}{suffix}"] = val
                            logger.debug(
                                f"[Ensemble] Mapped raw fact {elem} to {standard_key}{suffix} = {val}"
                            )

        logger.info(
            f"[Ensemble] Salvaged {total_facts} raw facts from edinet-mcp ({len(results)} unique keys)"
        )
        return results
    except Exception as e:
        logger.error(f"[Ensemble] edinet-mcp salvage failed: {e}", exc_info=True)
        return {}
    finally:
        if extract_dir.exists():
            try:
                shutil.rmtree(extract_dir)
                logger.info(f"[Ensemble] Cleaned up extraction directory {extract_dir}")
            except Exception as e:
                logger.warning(f"[Ensemble] Failed to clean up {extract_dir}: {e}")


def parse_with_edinet_tools(zip_path: Path, doc_id: str) -> Dict[str, Any]:
    """Brain 2: edinet-tools"""
    logger.info(f"[Ensemble] Running edinet-tools on {zip_path}")
    try:
        doc = MockDocument(zip_path, doc_id)
        report = parse_securities_report(doc)

        # Convert ParsedReport to dict
        raw_dict = {}
        if hasattr(report, "to_dict"):
            raw_dict = report.to_dict()
        else:
            # Fallback: extract attributes
            raw_dict = {
                attr: getattr(report, attr) for attr in dir(report) if not attr.startswith("_")
            }

        # Skipped debugging dump to optimize performance

        # Rename keys based on is_consolidated to avoid data contamination
        is_cons = raw_dict.get("is_consolidated", True)
        suffix = "_cons" if is_cons else "_non_cons"

        # List of financial items to rename
        financial_items = [
            "net_sales",
            "operating_income",
            "ordinary_income",
            "net_income",
            "prior_net_sales",
            "prior_operating_income",
            "prior_ordinary_income",
            "prior_net_income",
            "total_assets",
            "net_assets",
            "total_liabilities",
            "operating_cash_flow",
            "investing_cash_flow",
            "financing_cash_flow",
            "cash_and_deposits",
            "current_assets",
            "noncurrent_assets",
            "property_plant_equipment",
            "deferred_tax_assets",
            "current_liabilities",
            "accounts_payable_other",
            "retained_earnings",
        ]

        results = {}
        for k, v in raw_dict.items():
            if k in financial_items:
                results[f"{k}{suffix}"] = v
            else:
                results[k] = v

        return results
    except Exception as e:
        logger.error(f"[Ensemble] edinet-tools failed: {e}", exc_info=True)
        return {}


def parse_with_current_csv(csv_zip_path: Path | None, doc_id: str) -> Dict[str, Any]:
    """Brain 3: Current CSV Logic to salvage all numerical facts"""
    if not csv_zip_path or not csv_zip_path.exists():
        logger.info(f"[Ensemble] No CSV ZIP provided or found for {doc_id}")
        return {}

    logger.info(f"[Ensemble] Running Current CSV logic on {csv_zip_path}")
    try:
        from src.datalake.service.csv_parser import parse_edinet_csv

        with open(csv_zip_path, "rb") as f:
            content = f.read()
        csv_data = parse_edinet_csv(content)

        results = {}

        # Target items for direct mapping (Gate 0 fallback)
        target_tags = {
            "CurrentAssets": "current_assets",
            "CashAndDeposits": "cash_and_deposits",
            "CurrentLiabilities": "current_liabilities",
        }

        for _, df in csv_data.items():
            # EDINET CSV typically has:
            # Col 0: Item Name (JA), Col 1: Element Name (Tag), Col 2: Context, Col 3: Value

            for _, row in df.iterrows():
                vals = [str(v).strip() for v in row.values]
                if len(vals) < 4:
                    continue

                label_ja = vals[0]
                tag_name = vals[1]
                context = vals[2]
                val_str = vals[3]

                # Check if value is numeric
                cleaned_val = val_str.replace(",", "")
                if cleaned_val.isdigit() or (
                    cleaned_val.startswith("-") and cleaned_val[1:].isdigit()
                ):
                    int_val = int(cleaned_val)

                    # Use Tag name if available, otherwise fallback to JA label
                    key_base = tag_name if tag_name and tag_name != "nan" else label_ja

                    if key_base:
                        # 1. Full Salvage (EAV)
                        full_key = f"csv_{key_base}_{context}"
                        results[full_key] = int_val

                        # 2. Critical Mapping
                        if key_base in target_tags:
                            standard_key = target_tags[key_base]
                            suffix = "_cons" if "Consolidated" in context else "_non_cons"
                            results[f"{standard_key}{suffix}"] = int_val
                            logger.debug(
                                f"[Ensemble] CSV Mapped {key_base} to {standard_key}{suffix} = {int_val}"
                            )

        logger.info(f"[Ensemble] Salvaged {len(results)} facts from CSV")
        return results
    except Exception as e:
        logger.error(f"[Ensemble] Current CSV failed: {e}", exc_info=True)
        return {}


NARRATIVE_SECTION_MAP = {
    "BusinessRisksTextBlock": "business_risk",
    "ManagementPolicyBusinessEnvironmentIssuesToAddressTextBlock": "management_policy",
    "ResearchAndDevelopmentActivitiesTextBlock": "research_development",
    "AnalysisOfFinancialPositionOperatingResultsAndCashFlowsTextBlock": "mda",
}


def normalize_section_name(raw_key: str) -> str:
    """
    Normalizes XBRL TextBlock element IDs into standard lower snake_case keys.
    e.g., BusinessRisksTextBlock -> business_risk
          SomeOtherTextBlock -> some_other
    """
    if raw_key in NARRATIVE_SECTION_MAP:
        return NARRATIVE_SECTION_MAP[raw_key]

    # Fallback normalization: remove 'TextBlock' suffix and convert CamelCase to snake_case
    clean_key = raw_key
    if clean_key.endswith("TextBlock"):
        clean_key = clean_key[:-9]

    # CamelCase to snake_case
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", clean_key)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def ensemble_parse(xbrl_zip_path: Path, csv_zip_path: Path | None, doc_id: str) -> Dict[str, Any]:
    """
    Main entry point for Ensemble Parsing.
    Runs all 3 brains and merges the results.
    Uses edinet-tools as the base (primary) due to its strong XBRL parsing.
    """
    logger.info(f"[Ensemble] Starting ensemble parse for {doc_id}")

    # Brain 2: edinet-tools (Primary)
    base_data = parse_with_edinet_tools(xbrl_zip_path, doc_id)
    logger.info(f"[Ensemble] edinet-tools found {len(base_data)} items")

    # Brain 1: edinet-mcp (Secondary)
    mcp_data = parse_with_edinet_mcp(xbrl_zip_path, doc_id)
    logger.info(f"[Ensemble] edinet-mcp found {len(mcp_data)} items")

    # Brain 3: Current CSV (Tertiary)
    csv_data = parse_with_current_csv(csv_zip_path, doc_id)
    logger.info(f"[Ensemble] Current CSV found {len(csv_data)} items")

    # Extract qualitative text blocks
    narratives = {}

    # 1. Process edinet-tools text blocks (Primary)
    tools_text_blocks = base_data.get("text_blocks", {})
    if isinstance(tools_text_blocks, dict):
        for k, v in tools_text_blocks.items():
            if v and len(str(v)) > 20:
                normalized_key = normalize_section_name(k)
                markdown_content = clean_html_to_markdown(str(v))
                if markdown_content:
                    narratives[normalized_key] = markdown_content

    # 2. Process edinet-mcp text blocks (Secondary / Salvage fallback)
    for k, v in mcp_data.items():
        if "TextBlock" in k and v and len(str(v)) > 20:
            # key looks like 'raw_mcp_BusinessRisksTextBlock'
            raw_key = k.split("_")[-1]
            normalized_key = normalize_section_name(raw_key)
            if normalized_key not in narratives:
                markdown_content = clean_html_to_markdown(str(v))
                if markdown_content:
                    narratives[normalized_key] = markdown_content
                    logger.info(f"[Ensemble] Salvaged narrative '{normalized_key}' from edinet-mcp")

    # Return unmerged results for Silver layer separation
    # and narratives for file writing
    return {"mcp": mcp_data, "tools": base_data, "csv": csv_data, "narratives": narratives}
