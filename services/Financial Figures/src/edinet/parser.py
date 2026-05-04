import csv
import io
from typing import Any

from loguru import logger


class EDINETParser:
    """
    Parses EDINET statutory CSV files (Type 5).
    Handles both tab and comma delimiters and dynamically maps columns.
    """

    @staticmethod
    def parse_financial_csv(csv_content: str) -> list[dict[str, Any]]:
        """
        Parses a single financial CSV string into structured facts.
        """
        if not csv_content or not csv_content.strip():
            return []

        facts = []
        # Try tab first as it is the standard for EDINET statutory CSVs
        delimiter = "\t" if "\t" in csv_content else ","

        f = io.StringIO(csv_content.strip())
        reader = csv.reader(f, delimiter=delimiter)


        try:
            header = next(reader)
            # Find column indices dynamically
            id_idx = EDINETParser._find_col(header, ["要素ID", "Element ID", "vID"])
            name_idx = EDINETParser._find_col(header, ["項目名", "Element Name"])
            context_idx = EDINETParser._find_col(header, ["コンテキストID", "Context ID"])
            unit_idx = EDINETParser._find_col(header, ["単位", "Unit", "ユニット", "P"])
            val_idx = EDINETParser._find_col(header, ["値", "Value", "l"])

            # Fallback to defaults if headers not found (best effort)
            id_idx = 0 if id_idx is None else id_idx
            name_idx = 1 if name_idx is None else name_idx
            context_idx = 2 if context_idx is None else context_idx
            unit_idx = 3 if unit_idx is None else unit_idx
            val_idx = 4 if val_idx is None else val_idx

            row_count = 0
            for row in reader:
                row_count += 1
                if not row or len(row) <= max(id_idx, val_idx):
                    continue

                try:
                    element_id = row[id_idx].strip()
                    element_name = row[name_idx].strip() if name_idx < len(row) else ""
                    context_id = row[context_idx].strip() if context_idx < len(row) else ""
                    unit = row[unit_idx].strip() if unit_idx < len(row) else ""
                    raw_value = row[val_idx].strip()

                    if not raw_value or raw_value in ["-", "―", "－"]: # Handle various dash characters
                        continue

                    # Numeric cleaning
                    clean_val = raw_value.replace(",", "").replace("\u3000", "").replace(" ", "")
                    if clean_val.startswith("(") and clean_val.endswith(")"):
                        clean_val = "-" + clean_val[1:-1]
                    
                    if not clean_val:
                        continue

                    value = float(clean_val)
                    facts.append(
                        {
                            "id": element_id,
                            "name": element_name,
                            "context": context_id,
                            "unit": unit,
                            "value": value,
                            "raw_str": raw_value,
                        }
                    )

                except (ValueError, TypeError) as e:
                    # Very common in EDINET CSVs to have non-numeric values in numeric columns
                    logger.debug(f"Row {row_count} skipped: Not a numeric value ({e})")
                    continue
                except Exception as e:
                    logger.warning(f"Row {row_count} unexpected parse error: {e}")
                    # Don't fail the whole file sync, but log it
                    continue

            logger.info(f"[TRACE] Parsed {row_count} rows. Extracted {len(facts)} facts.")
            return facts

        except StopIteration:
            logger.warning("Empty CSV content encountered.")
            return []
        except Exception as e:
            logger.error(f"Critical failure during CSV parsing: {e}", exc_info=True)
            raise # Raise critical failure


    @staticmethod
    def _find_col(header: list[str], targets: list[str]) -> int | None:
        """Finds the index of a column that matches any of the targets."""
        for i, col in enumerate(header):
            for target in targets:
                if target in col:
                    return i
        return None
