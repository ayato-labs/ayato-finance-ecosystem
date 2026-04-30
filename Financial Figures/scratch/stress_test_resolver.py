import glob

import duckdb
import pandas as pd

from src.core.price_resolver import get_safe_price_view_sql


def stress_test_resolver():
    base_path = "C:/Users/saiha/My_Service/programing/finance/daily_stock_price/data/market_data/"
    files = glob.glob(f"{base_path}/**/*.parquet", recursive=True)

    if not files:
        print("No files found to test.")
        return

    # Select samples potentially with different schemas
    # We'll take first, middle, last to increase chance of diversity
    test_samples = [files[0], files[len(files) // 2], files[-1]]

    results = []

    conn = duckdb.connect(":memory:")

    for f in test_samples:
        # Detect Original Case
        cols = conn.execute(f"SELECT * FROM '{f}' LIMIT 0").df().columns.tolist()
        case_type = "Mixed/Upper" if any(c[0].isupper() for c in cols) else "Lower"

        # 1. Test OLD Logic (Fails if 'close' is not exact)
        success_old = False
        error_old = ""
        try:
            conn.execute(f"SELECT close FROM '{f}' LIMIT 1")
            success_old = True
        except Exception as e:
            error_old = str(e).split("\n")[0]

        # 2. Test NEW Logic (Resolver)
        success_new = False
        error_new = ""
        try:
            conn.execute(get_safe_price_view_sql(f))
            conn.execute("SELECT close FROM v_safe_prices LIMIT 1")
            success_new = True
        except Exception as e:
            error_new = str(e).split("\n")[0]

        results.append(
            {
                "File": f.split("\\")[-1],
                "Schema": case_type,
                "Old Logic (Fixed 'close')": "SUCCESS" if success_old else f"FAILED ({error_old})",
                "New Logic (Resolver)": "SUCCESS" if success_new else f"FAILED ({error_new})",
            }
        )

    df_results = pd.DataFrame(results)
    print("\n" + "=" * 100)
    print("ROBUSTNESS VERIFICATION: OLD VS NEW LOGIC")
    print("=" * 100)
    print(df_results)
    print("=" * 100 + "\n")

    # Final verdict
    all_new_success = all(r["New Logic (Resolver)"] == "SUCCESS" for r in results)
    if all_new_success:
        print(
            "VERDICT: The improvement is VALIDATED. The resolver handles varying schemas correctly."
        )
    else:
        print("VERDICT: FAILED. Some schemas still cause issues.")


if __name__ == "__main__":
    stress_test_resolver()
