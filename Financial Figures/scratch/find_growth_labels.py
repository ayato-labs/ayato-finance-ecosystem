import duckdb

from src.core.config import settings


def find_labels():
    # US
    print("\n--- US Market Growth Tags ---")
    conn_us = duckdb.connect(str(settings.DB_PATH_US), read_only=True)
    q_us = """
    SELECT DISTINCT tag, label 
    FROM company_facts 
    WHERE tag ILIKE '%Research%' 
       OR tag ILIKE '%Development%' 
       OR tag ILIKE '%CapitalExpenditure%'
       OR tag ILIKE '%PropertyPlant%'
    LIMIT 20
    """
    print(conn_us.execute(q_us).df().to_string(index=False))

    # JP
    print("\n--- JP Market Growth Tags ---")
    conn_jp = duckdb.connect(str(settings.DB_PATH_JP), read_only=True)
    # J-Quants V2 might use different conventions. Let's look for anything with "Research" or "Expenditure" in English.
    q_jp = """
    SELECT DISTINCT tag, label 
    FROM company_facts 
    WHERE tag ILIKE '%Research%' 
       OR tag ILIKE '%Development%'
       OR tag ILIKE '%Expenditure%'
       OR tag ILIKE '%Acquisition%'
       OR tag ILIKE '%Plant%'
    """
    df_jp = conn_jp.execute(q_jp).df()
    if df_jp.empty:
        print("No matches for specific keywords in JP. Listing top 50 tags to see patterns:")
        print(
            conn_jp.execute("SELECT DISTINCT tag, label FROM company_facts LIMIT 50")
            .df()
            .to_string(index=False)
        )
    else:
        print(df_jp.to_string(index=False))


if __name__ == "__main__":
    find_labels()
