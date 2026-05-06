import io
import zipfile
from loguru import logger

def get_csv_from_edinet(doc_id: str, api_key: str):
    """
    Fetches the ZIP containing CSV documents from EDINET API v2.
    Uses standard urllib to bypass environment-specific issues.
    """
    import urllib.request
    import urllib.error
    import time

    url = f"https://api.edinet-fsa.go.jp/api/v2/documents/{doc_id}?type=5&Subscription-Key={api_key}"
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.debug(f"Fetching CSV from EDINET: {doc_id} (Attempt {attempt + 1})")
            with urllib.request.urlopen(url, timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 2 ** attempt
                logger.warning(f"Rate limited (429). Waiting {wait}s...")
                time.sleep(wait)
                continue
            logger.error(f"HTTP Error {e.code} for {doc_id}")
            return None
        except Exception as e:
            logger.error(f"Failed to fetch {doc_id}: {e}")
            return None
    return None

def parse_edinet_csv(content: bytes):
    """
    Unzips and parses CSV files from the bytes content.
    Returns a dictionary mapping filename to DataFrame.
    """
    import pandas as pd
    
    if not content:
        return {}

    try:
        results = {}
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            for file_name in z.namelist():
                if file_name.endswith(".csv"):
                    with z.open(file_name) as f:
                        # Skip first line (header info) and use second line as columns
                        try:
                            df = pd.read_csv(f, encoding="shift_jis", skiprows=1)
                            results[file_name] = df
                        except Exception as e:
                            logger.warning(f"Failed to parse CSV {file_name}: {e}")
        return results
    except zipfile.BadZipFile:
        logger.error("Failed to unzip: Not a valid ZIP file.")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error in parse_edinet_csv: {e}")
        return {}
