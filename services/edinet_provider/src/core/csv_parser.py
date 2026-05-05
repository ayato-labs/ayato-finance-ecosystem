import io
import time
import zipfile

import chardet
import pandas as pd
from loguru import logger


def get_csv_from_edinet(doc_id, api_key, max_retries=5):
    import requests

    url = f"https://api.edinet-fsa.go.jp/api/v2/documents/{doc_id}"
    params = {"type": 5, "Subscription-Key": api_key}

    for attempt in range(max_retries):
        try:
            logger.debug(f"Downloading CSV for {doc_id} (Attempt {attempt+1}/{max_retries})...")
            response = requests.get(url, params=params, timeout=30)

            if response.status_code == 200:
                content = response.content
                if b"message" in content or b"statusCode" in content:
                    # Check for 429 inside 200-OK body (some APIs do this)
                    if b"429" in content or b"Rate limit" in content:
                        raise requests.exceptions.HTTPError("429 Rate Limit Exceeded (in body)")
                    logger.warning(f"API returned logical error in body for {doc_id}: {response.text}")
                    return None
                return content

            if response.status_code == 429:
                # Exponential backoff: 1s, 2s, 4s, 8s, 16s
                wait_time = 2**attempt
                logger.warning(f"⚠️ 429 Rate Limit for {doc_id}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue

            logger.warning(
                f"API request failed for {doc_id} with status {response.status_code}: {response.text}"
            )
            return None

        except (requests.exceptions.RequestException, requests.exceptions.HTTPError) as e:
            if attempt == max_retries - 1:
                logger.error(f"❌ Max retries reached for {doc_id}: {e}")
                return None
            wait_time = 2**attempt
            logger.debug(f"Transient error for {doc_id}: {e}. Retrying in {wait_time}s...")
            time.sleep(wait_time)

    return None


def parse_edinet_csv(content):
    if not content:
        return {}
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
                            continue

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
                except Exception as e:
                    logger.warning(f"Failed to parse {csv_file}: {e}")
            return results
    except Exception as e:
        logger.error(f"ZIP parse error: {e}", exc_info=True)
        return {}
