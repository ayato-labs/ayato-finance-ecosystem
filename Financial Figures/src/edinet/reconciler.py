import logging
from typing import Any

logger = logging.getLogger(__name__)


class EDINETReconciler:
    """
    Stage 2 Mapping: Deterministically reconciles data between J-Quants and EDINET.
    Priority: Accuracy and Auditability.
    """

    def __init__(self, tolerance: float = 1000.0):
        # Allowable margin of error for rounding differences.
        # Default 1000 Yen (extremely strict for financial data).
        self.tolerance = tolerance
        logger.info(f"EDINETReconciler initialized with tolerance={self.tolerance}")

    def reconcile_fact(self, label: str, val_jquants: float, val_edinet: float) -> dict[str, Any]:
        """
        Rule-based reconciliation of a single financial fact.
        Returns a dictionary including strategy and reasoning for audit logs.
        """
        diff = abs(val_jquants - val_edinet)
        logger.info(f"[RECON] Comparing {label}: J={val_jquants}, E={val_edinet} (Diff={diff})")

        # Rule 1: Near-exact match
        if diff <= self.tolerance:
            return {
                "strategy": "KEEP_EDINET",
                "merged_val": val_edinet,
                "reasoning": f"Values are nearly identical (diff={diff} <= {self.tolerance}). Trusting EDINET statutory filing.",
            }

        # Rule 2: Unit mismatch detection (1000x or 1,000,000x)
        if val_edinet != 0:
            ratio = val_jquants / val_edinet
            if abs(ratio - 1000) < 0.1 or abs(ratio - 1000000) < 0.1:
                logger.warning(f"[RECON] Unit mismatch detected for {label}: Ratio={ratio}")
                return {
                    "strategy": "UNIT_SCALED_EDINET",
                    "merged_val": val_jquants,
                    "reasoning": f"Detected {ratio:.0f}x scale difference. Using J-Quants scaled value.",
                }

        # Rule 3: Significant mismatch
        logger.warning(f"[RECON] Significant mismatch for {label}: J={val_jquants}, E={val_edinet}")
        return {
            "strategy": "OVERRIDE_WITH_EDINET",
            "merged_val": val_edinet,
            "reasoning": (
                f"Significant discrepancy ({diff}). "
                "EDINET statutory report overrides J-Quants preliminary summary."
            ),
        }

    def reconcile_batch(
        self, ticker: str, date_str: str, facts: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Reconciles a batch of facts and produces audit records."""
        results = []
        logger.info(f"[RECON] Reconciling batch for {ticker} on {date_str} ({len(facts)} labels)")

        for item in facts:
            label = item["label"]
            j_val = item.get("jquants")
            e_val = item.get("edinet")

            if j_val is not None and e_val is not None:
                res = self.reconcile_fact(label, j_val, e_val)
                # Combine for audit storage
                results.append(
                    {
                        "code": ticker,
                        "disclosed_date": date_str,
                        "label": label,
                        "jquants_val": j_val,
                        "edinet_val": e_val,
                        "merged_val": res["merged_val"],
                        "strategy": res["strategy"],
                        "reasoning": res["reasoning"],
                    }
                )
            elif e_val is not None:
                results.append(
                    {
                        "code": ticker,
                        "disclosed_date": date_str,
                        "label": label,
                        "jquants_val": None,
                        "edinet_val": e_val,
                        "merged_val": e_val,
                        "strategy": "ONLY_EDINET",
                        "reasoning": "Data only available in EDINET.",
                    }
                )
            elif j_val is not None:
                results.append(
                    {
                        "code": ticker,
                        "disclosed_date": date_str,
                        "label": label,
                        "jquants_val": j_val,
                        "edinet_val": None,
                        "merged_val": j_val,
                        "strategy": "ONLY_JQUANTS",
                        "reasoning": "Data only available in J-Quants.",
                    }
                )

        return results
