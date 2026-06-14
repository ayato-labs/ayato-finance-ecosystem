import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class DataValidator:
    """
    Validates the quality and completeness of extracted financial data.
    Ensures that garbage data does not pollute the DataLake.
    """

    def __init__(self, tolerance: float = 1000.0):
        """
        Args:
            tolerance: Allowed difference for accounting equations (in yen).
                       Default 1000 yen to account for rounding errors.
        """
        self.tolerance = tolerance

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates a merged financial document.

        Returns:
            A dict with validation results, scores, and warnings.
        """
        report = {
            "doc_id": data.get("__ensemble_metadata", {}).get("doc_id", "Unknown"),
            "is_valid": True,
            "quality_score": 100,
            "checks": {
                "critical_fields_present": True,
                "accounting_equation_valid": True,
                "no_negative_assets_or_sales": True,
            },
            "missing_fields": [],
            "warnings": [],
        }

        # Determine if consolidated or non-consolidated
        # Check both since ensemble might have filled both or one
        has_cons = any(k.endswith("_cons") for k in data.keys())
        has_non_cons = any(k.endswith("_non_cons") for k in data.keys())

        suffixes = []
        if has_cons:
            suffixes.append("_cons")
        if has_non_cons:
            suffixes.append("_non_cons")

        # If no suffixes found, use raw keys (fallback)
        if not suffixes:
            suffixes.append("")

        # 1. Critical Fields Check (Fill Rate)
        # We require at least one set of critical fields (either cons or non_cons)
        # to be present if both are detected, or just the present one.

        missing_by_suffix = {}
        for suffix in suffixes:
            missing_by_suffix[suffix] = []
            required = [f"net_sales{suffix}", f"total_assets{suffix}"]
            for field in required:
                if field not in data or data[field] is None:
                    missing_by_suffix[suffix].append(field)

        # If all suffixes failed to provide critical fields, it's a fail
        all_failed = True
        for _suffix, missing in missing_by_suffix.items():
            if not missing:
                all_failed = False
                break
            report["missing_fields"].extend(missing)

        if all_failed:
            report["checks"]["critical_fields_present"] = False
            report["quality_score"] -= 30
            report["is_valid"] = False
            report["warnings"].append("Missing critical fields for all detected scopes.")
        elif any(len(m) > 0 for m in missing_by_suffix.values()):
            # Some scope is missing fields, but at least one is complete
            report["warnings"].append(
                "Some reporting scopes (Consolidated or Non-Consolidated) are missing critical fields, but at least one is complete."
            )

        # 2. Accounting Equation Check: Assets = Liabilities + Net Assets
        for suffix in suffixes:
            assets = data.get(f"total_assets{suffix}")
            liabilities = data.get(f"total_liabilities{suffix}")
            net_assets = data.get(f"net_assets{suffix}")

            if assets is not None and liabilities is not None and net_assets is not None:
                diff = abs(assets - (liabilities + net_assets))
                if diff > self.tolerance:
                    report["checks"]["accounting_equation_valid"] = False
                    report["quality_score"] -= 20
                    report["warnings"].append(
                        f"Accounting equation imbalance ({suffix}): Assets({assets}) != Liabilities({liabilities}) + NetAssets({net_assets}). Diff: {diff}"
                    )
            elif assets is not None or liabilities is not None or net_assets is not None:
                # Some are present but not all
                report["warnings"].append(
                    f"Cannot verify accounting equation for {suffix} due to missing components."
                )

        # 3. Sign Check (Negative Assets or Sales are usually errors)
        for suffix in suffixes:
            for field in [f"net_sales{suffix}", f"total_assets{suffix}", f"net_assets{suffix}"]:
                val = data.get(field)
                if val is not None and val < 0:
                    # Net income can be negative (loss), but sales and assets rarely are.
                    if "net_sales" in field or "total_assets" in field:
                        report["checks"]["no_negative_assets_or_sales"] = False
                        report["quality_score"] -= 20
                        report["warnings"].append(f"Negative value detected for {field}: {val}")

        # Final score adjustments
        report["quality_score"] = max(0, report["quality_score"])

        # Brain contribution analysis
        meta = data.get("__ensemble_metadata", {})
        report["brains_contribution"] = meta.get("brains", {})

        return report
