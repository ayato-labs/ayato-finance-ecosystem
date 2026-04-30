import duckdb
import pandas as pd

from src.core.config import settings


def research_jp_tags():
    print("Investigating JP Growth Tags (Correct Encoding)...")
    conn_jp = duckdb.connect(str(settings.DB_PATH_JP), read_only=True)

    # Use hex or just rely on Python's string handling
    keywords = ["研究", "開発", "設備", "有形固定資産"]

    # Get all tags and filter in Python to be safe with encoding
    df = conn_jp.execute("SELECT DISTINCT taxonomy, tag, label FROM company_facts").df()

    results = []
    for kw in keywords:
        found = df[df["label"].str.contains(kw, na=False, case=False)]
        results.append(found)

    final_df = pd.concat(results).drop_duplicates()
    if not final_df.empty:
        print(final_df.to_string(index=False))
    else:
        print("No matches found in JP database.")


if __name__ == "__main__":
    research_jp_tags()
