import io
import zipfile
import pandas as pd
import chardet
from loguru import logger


def get_csv_from_edinet(doc_id, api_key):
    import requests

    url = f"https://api.edinet-fsa.go.jp/api/v2/documents/{doc_id}"
    params = {"type": 5, "Subscription-Key": api_key}

    logger.debug(f"Downloading CSV for doc_id: {doc_id}...")
    try:
        response = requests.get(url, params=params, timeout=30)

        # Check if API returned successful status AND no error message in JSON body
        if response.status_code == 200:
            content = response.content
            # Some APIs return 200 even for errors with JSON payload
            if b"message" in content or b"statusCode" in content:
                logger.warning(f"API returned logical error in body for {doc_id}: {response.text}")
                return None

            logger.debug(f"Successfully downloaded CSV content for {doc_id} ({len(content)} bytes)")
            return content

        logger.warning(
            f"API request failed for {doc_id} with status {response.status_code}: {response.text}"
        )
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error while fetching CSV for {doc_id}: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching CSV for {doc_id}: {e}", exc_info=True)
        return None


def parse_edinet_csv(content):
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            csv_files = [f for f in z.namelist() if f.endswith(".csv")]
            results = {}

            if not csv_files:
                logger.debug("No CSV files found in the ZIP archive.")
                return results

            for csv_file in csv_files:
                try:
                    with z.open(csv_file) as f:
                        raw_data = f.read()
                        if not raw_data:
                            logger.debug(f"Skipping empty CSV file: {csv_file}")
                            continue

                        # Use chardet for robust encoding detection
                        detection = chardet.detect(raw_data[:10000])
                        encoding = detection.get("encoding")
                        confidence = detection.get("confidence", 0)

                        if not encoding or confidence < 0.7:
                            if raw_data.startswith(b"\xff\xfe") or raw_data.startswith(b"\xfe\xff"):
                                encoding = "utf-16"
                            else:
                                encoding = "shift-jis"

                        text = raw_data.decode(encoding, errors="replace")
                        sep = "\t" if "\t" in text[:1000] else ","

                        df = pd.read_csv(
                            io.StringIO(text),
                            skiprows=1,
                            sep=sep,
                            on_bad_lines="skip",
                            engine="python",
                        )
                        results[csv_file] = df
                        logger.debug(f"Successfully parsed {csv_file} ({len(df)} rows)")
                except Exception as e:
                    logger.warning(
                        f"Failed to parse {csv_file} with detected encoding {encoding}: {e}"
                    )
                    # Last resort fallback
                    try:
                        text = raw_data.decode("shift-jis", errors="ignore")
                        df = pd.read_csv(io.StringIO(text), skiprows=1, sep=",", engine="python")
                        results[csv_file] = df
                        logger.debug(f"Fallback parse successful for {csv_file}")
                    except Exception as e2:
                        logger.error(
                            f"Last resort fallback failed for {csv_file}: {e2}", exc_info=True
                        )
            return results
    except zipfile.BadZipFile as e:
        logger.error(f"Invalid ZIP file provided to parser: {e}", exc_info=True)
        return {}
    except Exception as e:
        logger.error(f"Unexpected error in parse_edinet_csv: {e}", exc_info=True)
        return {}
