import duckdb
import pandas as pd
import numpy as np

conn = duckdb.connect("test_crash.duckdb")
conn.execute("DROP TABLE IF EXISTS company_facts")
conn.execute("""
CREATE TABLE company_facts (
    accession_number VARCHAR,
    fiscal_year SMALLINT,
    fiscal_period VARCHAR,
    label VARCHAR,
    value DOUBLE,
    unit VARCHAR,
    is_standardized BOOLEAN,
    raw_tag VARCHAR,
    ingested_at TIMESTAMP,
    PRIMARY KEY (accession_number, label)
);
""")

print("Creating fake data...")
n = 100000
df = pd.DataFrame({
    "accession_number": ["ACC-1"] * n,
    "fiscal_year": [2024] * n,
    "fiscal_period": ["FY"] * n,
    "label": [f"label_{i}" for i in range(n)],
    "value": np.random.rand(n),
    "unit": ["USD"] * n,
    "is_standardized": [True] * n,
    "raw_tag": ["tag"] * n
})

print("Testing conn.append to TEMP table...")
conn.execute("CREATE TEMP TABLE tmp_c AS SELECT * FROM company_facts LIMIT 0")
df["ingested_at"] = pd.Timestamp.now()
conn.append("tmp_c", df)
conn.execute("""
    INSERT OR REPLACE INTO company_facts
    SELECT * FROM tmp_c
""")
print("Append + INSERT OR REPLACE done. Size:", conn.execute("SELECT count(*) FROM company_facts").fetchone()[0])
print("Test passed.")

