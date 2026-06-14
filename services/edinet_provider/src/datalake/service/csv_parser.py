import io
import time
import urllib.error
import urllib.request
import zipfile

import pandas as pd
from loguru import logger

from src.datalake.shared.infra.config import settings
from src.datalake.shared.infra.rate_limit import edinet_rate_limit


def get_document_from_edinet(doc_id: str, api_key: str, doc_type: int = 5):
    """
    Fetches the ZIP containing documents from EDINET API v2.
    doc_type: 1 for XBRL, 5 for CSV.
    All data is kept in memory. Caching has been completely abandoned.
    """
    url = f"https://api.edinet-fsa.go.jp/api/v2/documents/{doc_id}?type={doc_type}&Subscription-Key={api_key}"
    suffix = "csv" if doc_type == 5 else "xbrl"
    max_retries = 3

    for attempt in range(max_retries):
        # Global rate limit check
        edinet_rate_limit.check_and_wait()
        
        try:
            logger.debug(f"Fetching {suffix}: {doc_id} (Attempt {attempt + 1}/{max_retries})")
            with urllib.request.urlopen(url, timeout=30) as response:
                content = response.read()

                # Check if it is a JSON error response representing a 429
                if not content.startswith(b"PK\x03\x04"):
                    if b"429" in content or b"Too Many Requests" in content:
                        logger.warning(f"Rate limited (429 JSON) for {doc_id}. Triggering global backoff.")
                        edinet_rate_limit.trigger_backoff(60.0)
                        continue
                        
                    logger.warning(
                        f"Received non-ZIP content from EDINET for {doc_id}. "
                        f"First 100 bytes: {content[:100]!r}"
                    )
                    continue

                logger.debug(
                    f"Successfully fetched {suffix} for {doc_id}, size: {len(content)} bytes"
                )
                return content

        except urllib.error.HTTPError as e:
            if e.code == 429:
                logger.warning(f"Rate limited (429 HTTP) for {doc_id}. Triggering global backoff.")
                edinet_rate_limit.trigger_backoff(60.0)
                continue
            logger.error(f"HTTP Error {e.code} for {doc_id}: {e.reason}", exc_info=True)
            return None
        except Exception as e:
            logger.error(
                f"Failed to fetch {doc_id} on attempt {attempt + 1}: {e}",
                exc_info=True,
            )
            if attempt == max_retries - 1:
                return None
            time.sleep(1.5)
    return None


def get_csv_from_edinet(doc_id: str, api_key: str):
    """CSV document fetch wrapper."""
    return get_document_from_edinet(doc_id, api_key, doc_type=5)


def get_dual_documents_from_edinet(doc_id: str, api_key: str):
    """Fetches both XBRL (type=1) and CSV (type=5) from EDINET."""
    logger.info(f"Fetching dual documents (XBRL + CSV) for {doc_id}")
    xbrl_content = get_document_from_edinet(doc_id, api_key, doc_type=1)
    csv_content = get_document_from_edinet(doc_id, api_key, doc_type=5)
    return xbrl_content, csv_content


def parse_edinet_csv(content: bytes):
    """
    Unzips and parses CSV files from the bytes content.
    Returns a dictionary mapping filename to DataFrame.
    """
    if not content:
        return {}

    try:
        results = {}
        # Basic ZIP validation (Magic number: PK)
        if not content.startswith(b"PK\x03\x04"):
            logger.warning(
                "Received non-ZIP content from EDINET (Magic number mismatch). "
                f"First 100 bytes: {content[:100]!r}"
            )
            return {}

        try:
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                for file_name in z.namelist():
                    if file_name.endswith(".csv"):
                        try:
                            with z.open(file_name) as f:
                                raw_data = f.read()
                                if not raw_data:
                                    continue

                                # Detect encoding
                                encoding = "cp932"
                                sep = ","

                                # Try UTF-16 first
                                try:
                                    raw_data.decode("utf-16")
                                    encoding = "utf-16"
                                    sep = "\t"
                                except UnicodeDecodeError:
                                    if raw_data.startswith(b"\xef\xbb\xbf"):
                                        encoding = "utf-8-sig"

                                # Use io.BytesIO to feed back to pandas
                                df = pd.read_csv(
                                    io.BytesIO(raw_data),
                                    encoding=encoding,
                                    sep=sep,
                                    skiprows=1,
                                    on_bad_lines="skip",
                                    encoding_errors="replace",
                                )
                                results[file_name] = df
                        except Exception as e:
                            logger.error(
                                f"Failed to parse CSV {file_name}: {e}",
                                exc_info=True
                            )
        except zipfile.BadZipFile:
            logger.warning(
                f"Content is not a valid ZIP file. Skipping. First 100 bytes: {content[:100]!r}"
            )
        return results
    except Exception as e:
        logger.error(f"Unexpected error in parse_edinet_csv: {e}", exc_info=True)
        return {}
