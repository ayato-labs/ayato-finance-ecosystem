import duckdb

from src.core.config import settings


def research_growth_tags():
    # US Database
    print("\n" + "=" * 80)
    print("US MARKET: INVESTIGATING GROWTH-RELATED TAGS (SEC)")
    print("=" * 80)
    conn_us = duckdb.connect(str(settings.DB_PATH_US), read_only=True)

    us_queries = {
        "Research & Development": "SELECT DISTINCT taxonomy, tag, label FROM company_facts WHERE tag ILIKE '%Research%' OR tag ILIKE '%Development%' LIMIT 15",
        "Property, Plant & Equipment (CapEx)": "SELECT DISTINCT taxonomy, tag, label FROM company_facts WHERE tag ILIKE '%PropertyPlant%' OR tag ILIKE '%AcquisitionOfP%' OR tag ILIKE '%CapitalExpenditure%' LIMIT 15",
    }

    for category, query in us_queries.items():
        print(f"\n--- {category} ---")
        try:
            df = conn_us.execute(query).df()
            if not df.empty:
                print(df.to_string(index=False))
            else:
                print("No tags found in current sync sample.")
        except Exception as e:
            print(f"Error: {e}")

    # JP Database
    print("\n" + "=" * 80)
    print("JP MARKET: INVESTIGATING GROWTH-RELATED TAGS (J-Quants)")
    print("=" * 80)
    conn_jp = duckdb.connect(str(settings.DB_PATH_JP), read_only=True)

    jp_queries = {
        "Research & Development (研究開発)": "SELECT DISTINCT taxonomy, tag, label FROM company_facts WHERE tag ILIKE '%Research%' OR label ILIKE '%研究%' OR label ILIKE '%開発%' LIMIT 15",
        "Capital Expenditure (設備投資)": "SELECT DISTINCT taxonomy, tag, label FROM company_facts WHERE tag ILIKE '%CapEx%' OR label ILIKE '%設備%' OR label ILIKE '%有形固定資産%' LIMIT 15",
    }

    for category, query in jp_queries.items():
        print(f"\n--- {category} ---")
        try:
            df = conn_jp.execute(query).df()
            if not df.empty:
                print(df.to_string(index=False))
            else:
                print("No tags found in current sync sample.")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    research_growth_tags()
