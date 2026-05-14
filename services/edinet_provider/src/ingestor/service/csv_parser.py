import io
import time
import urllib.error
import urllib.request
import zipfile

import pandas as pd
import zstandard as zstd
from loguru import logger

from src.shared.infra.config import settings


def get_csv_from_edinet(doc_id: str, api_key: str, cache_writer=None):
    """
    Fetches the ZIP containing CSV documents from EDINET API v2 or local cache.
    Uses standard urllib to bypass environment-specific issues, and Zstandard
    for local raw data caching.
    """
    settings.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = settings.RAW_DATA_DIR / f"{doc_id}_csv.zip.zst"

    # Try loading from cache first
    if cache_path.exists():
        try:
            logger.debug(f"Loading cached raw CSV for {doc_id}...")
            with open(cache_path, "rb") as f:
                dctx = zstd.ZstdDecompressor()
                return dctx.decompress(f.read())
        except Exception as e:
            logger.warning(
                f"Failed to read cache for {doc_id}, falling back to API: {e}", exc_info=True
            )

    url = (
        f"https://api.edinet-fsa.go.jp/api/v2/documents/{doc_id}?type=5&Subscription-Key={api_key}"
    )

    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.debug(f"Fetching CSV: {doc_id} (Attempt {attempt + 1}/{max_retries})")
            with urllib.request.urlopen(url, timeout=30) as response:
                content = response.read()
                logger.debug(f"Successfully fetched CSV for {doc_id}, size: {len(content)} bytes")

                # Cache the raw content with zstd asynchronously if writer is provided
                if cache_writer is not None:
                    cache_writer.put(doc_id, content)
                else:
                    # Fallback to synchronous writing if no queue is available
                    try:
                        cctx = zstd.ZstdCompressor(level=settings.ZSTD_COMPRESSION_LEVEL)
                        with open(cache_path, "wb") as f:
                            f.write(cctx.compress(content))
                        logger.debug(
                            "Cached raw CSV for {doc_id} to {cache_path} (level {level})",
                            doc_id=doc_id,
                            cache_path=cache_path,
                            level=settings.ZSTD_COMPRESSION_LEVEL,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to cache raw CSV for {doc_id}: {e}", exc_info=True)

                return content
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 2**attempt
                logger.warning(
                    f"Rate limited (429) on attempt {attempt + 1} for {doc_id}. Waiting {wait}s..."
                )
                time.sleep(wait)
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
            time.sleep(1)
    return None


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

        with zipfile.ZipFile(io.BytesIO(content)) as z:
            for file_name in z.namelist():
                if file_name.endswith(".csv"):
                    try:
                        with z.open(file_name) as f:
                            raw_data = f.read()
                            if not raw_data:
                                continue

                            # Detect encoding by BOM
                            encoding = "cp932"
                            sep = ","
                            if raw_data.startswith(b"\xff\xfe"):
                                encoding = "utf-16"
                                sep = "\t"
                            elif raw_data.startswith(b"\xef\xbb\xbf"):
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
                            "Failed to parse CSV {filename}: {error}",
                            filename=file_name,
                            error=str(e),
                            exc_info=True,
                            extra={"file_name": file_name},
                        )
        return results
    except zipfile.BadZipFile:
        logger.error("Failed to unzip: Not a valid ZIP file.")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error in parse_edinet_csv: {e}", exc_info=True)
        return {}
