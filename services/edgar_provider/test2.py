import sys, time
import zipfile, json
import pandas as pd
import duckdb
from edgar_provider.engine import parse_company_facts_json

print('Start', flush=True)
z = zipfile.ZipFile('data/companyfacts.zip')
content = z.read('CIK0000001750.json').decode('utf-8')
records = parse_company_facts_json('CIK0000001750.json', content, {'0000001750': 'AIR'}, 'test')

df = pd.DataFrame(records, columns=['ticker', 'cik', 'accession_number', 'form', 'filed_date', 'fiscal_year', 'fiscal_period', 'label', 'value', 'unit', 'is_standardized', 'raw_tag', 'session_id'])
df.drop_duplicates(subset=['ticker', 'accession_number', 'label'], keep='last', inplace=True)
df['filed_date'] = pd.to_datetime(df['filed_date']).dt.date
df['value'] = pd.to_numeric(df['value'], errors='coerce').fillna(0.0)

conn = duckdb.connect('data/facts.duckdb', read_only=False)

print('Dropping index...', flush=True)
conn.execute('DROP INDEX IF EXISTS idx_us_facts_lookup;')

print(f'Trying to insert {len(df)} records into DuckDB without secondary index...', flush=True)
try:
    conn.execute('INSERT OR REPLACE INTO company_facts (ticker, cik, accession_number, form, filed_date, fiscal_year, fiscal_period, label, value, unit, is_standardized, raw_tag, session_id, ingested_at) SELECT *, CURRENT_TIMESTAMP FROM df')
    print('SUCCESS', flush=True)
except Exception as e:
    print(f'ERROR: {e}', flush=True)
finally:
    conn.close()
