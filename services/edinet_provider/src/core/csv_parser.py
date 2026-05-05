import io
import zipfile
import pandas as pd
import chardet
from loguru import logger

def get_csv_from_edinet(doc_id, api_key):
    import requests
    url = f"https://api.edinet-fsa.go.jp/api/v2/documents/{doc_id}"
    params = {"type": 5, "Subscription-Key": api_key}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.content
    return None

def parse_edinet_csv(content):
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        csv_files = [f for f in z.namelist() if f.endswith('.csv')]
        results = {}
        for csv_file in csv_files:
            with z.open(csv_file) as f:
                raw_data = f.read()
                if not raw_data:
                    continue

                # 1. Use chardet for robust encoding detection
                detection = chardet.detect(raw_data[:10000]) # Sample first 10k
                encoding = detection.get('encoding')
                confidence = detection.get('confidence', 0)

                # Fallback heuristics
                if not encoding or confidence < 0.7:
                    if raw_data.startswith(b'\xff\xfe') or raw_data.startswith(b'\xfe\xff'):
                        encoding = 'utf-16'
                    else:
                        encoding = 'shift-jis'

                try:
                    text = raw_data.decode(encoding, errors='replace')
                    # Detect separator (TSV vs CSV)
                    sep = '\t' if '\t' in text[:1000] else ','
                    
                    # Read with flexible options
                    df = pd.read_csv(
                        io.StringIO(text), 
                        skiprows=1, 
                        sep=sep, 
                        on_bad_lines='skip',
                        engine='python'
                    )
                    results[csv_file] = df
                except Exception as e:
                    logger.warning(f"Failed to parse {csv_file} with {encoding}: {e}")
                    
                    # Last resort fallback to shift-jis with ignore
                    try:
                        text = raw_data.decode('shift-jis', errors='ignore')
                        df = pd.read_csv(io.StringIO(text), skiprows=1, sep=',', engine='python')
                        results[csv_file] = df
                    except Exception as e:
                        logger.debug(f"Last resort fallback failed for {csv_file}: {e}")
                        pass
        return results
