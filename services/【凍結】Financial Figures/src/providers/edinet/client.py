import io
import zipfile
from datetime import date
from pathlib import Path

import requests
from loguru import logger

from src.core.config import settings


class EDINETClient:
    """
    Client for EDINET API (V2).
    Handles document listing and statutory CSV downloads.
    """

    BASE_URL = "https://api.edinet-fsa.go.jp/api/v2"
    MIN_CONTENT_SIZE = 100

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.EDINET_API_KEY
        if not self.api_key:
            logger.error("CRITICAL: EDINET_API_KEY is missing. Operations will fail.")
            raise ValueError("EDINET_API_KEY is required for statutory data access.")
        logger.info("EDINETClient initialized with API Key.")

    def get_document_list(self, target_date: date) -> dict:
        """Fetch document list for a specific date with full traceability."""
        url = f"{self.BASE_URL}/documents.json"
        params = {
            "date": target_date.strftime("%Y-%m-%d"),
            "type": 2,
            "Subscription-Key": self.api_key,
        }

        logger.info(f"[TRACE] Requesting document list for date={params['date']} type=2")
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            metadata = data.get("metadata") or {}
            res_code = metadata.get("resultCode")
            count = len(data.get("results", []))

            logger.info(f"[TRACE] Received response: count={count}, resultCode={res_code}")

            res_code_str = str(res_code) if res_code is not None else ""
            if res_code_str != "200":
                if count == 0 and not res_code_str:
                    logger.debug(
                        f"EDINET API returned empty results with no resultCode for {target_date}."
                    )
                elif res_code_str == "404":
                    logger.info(f"EDINET API returned 404 (No data) for {target_date}.")
                else:
                    logger.warning(f"EDINET API returned non-200 resultCode: {res_code}")

            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during document list fetch: {e}", exc_info=True)
            raise RuntimeError(f"Failed to fetch EDINET document list for {target_date}") from e

    def download_document_csv(self, doc_id: str) -> bytes | None:
        """Download CSV zip for a specific document ID (Type 5)."""
        url = f"{self.BASE_URL}/documents/{doc_id}"
        params = {"type": 5, "Subscription-Key": self.api_key}

        logger.info(f"[TRACE] Downloading statutory CSV for doc_id={doc_id}")
        try:
            response = requests.get(url, params=params, timeout=60)
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type.lower() or response.content.startswith(b"{"):
                try:
                    data = response.json()
                    msg = data.get("metadata", {}).get("message", response.text[:100])
                    logger.warning(
                        f"[SKIP] Doc {doc_id} does not contain CSV data (API Message: {msg})"
                    )
                except Exception:
                    logger.warning(
                        f"[SKIP] Doc {doc_id} returned JSON instead of ZIP. "
                        f"Content: {response.text[:100]}"
                    )
                return None

            content_size = len(response.content)
            logger.info(f"[TRACE] Download complete: doc_id={doc_id}, size={content_size} bytes")

            if content_size < self.MIN_CONTENT_SIZE:
                logger.warning(
                    f"Doc {doc_id} returned suspiciously small content ({content_size}b)"
                )

            # Validate that the downloaded bytes form a legitimate ZIP file.
            if not zipfile.is_zipfile(io.BytesIO(response.content)):
                logger.warning(
                    f"[SKIP] Doc {doc_id} is not a valid ZIP file "
                    f"(Content-Type: {content_type}, Size: {content_size}b)."
                )
                return None

            return response.content

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download EDINET CSV zip for {doc_id}: {e}", exc_info=True)
            raise RuntimeError(f"EDINET Download Failure: {doc_id}") from e

    def extract_csv_from_zip(self, zip_content: bytes) -> list[tuple[str, str]]:
        """Extract CSV files from zip with integrity logging."""
        csv_files = []
        try:
            with zipfile.ZipFile(io.BytesIO(zip_content)) as z:
                files = z.namelist()
                logger.info(f"[TRACE] Zip opened. Contains {len(files)} files.")

                for filename in files:
                    if filename.endswith(".csv"):
                        with z.open(filename) as f:
                            # EDINET statutory CSVs are UTF-16 with BOM typically
                            content = f.read().decode("utf-16")
                            csv_files.append((filename, content))
                            logger.info(f"[TRACE] Extracted CSV: {filename} ({len(content)} chars)")

            if not csv_files:
                logger.warning("No CSV files found in the downloaded zip package.")

            return csv_files

        except zipfile.BadZipFile as e:
            logger.error(f"Downloaded content is not a valid ZIP file: {e}")
            raise ValueError("Corrupt ZIP content from EDINET API.") from e
        except Exception as e:
            logger.error(f"Unexpected error during ZIP extraction: {e}", exc_info=True)
            raise

    def download_edinet_code_list(self, dest_dir: Path) -> Path:
        """
        Download the latest EdinetcodeDlInfo.zip and extract EdinetcodeDlInfo.csv.
        Returns the path to the extracted CSV.
        """
        url = settings.EDINET_MASTER_URL
        logger.info(f"Downloading EDINET code master from {url}")

        headers = {"User-Agent": "Mozilla/5.0"}  # Required for disclosure2dl domain
        try:
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()

            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                # Find the CSV file in the zip
                csv_files = [f for f in z.namelist() if f.endswith(".csv")]
                if not csv_files:
                    raise FileNotFoundError("EdinetcodeDlInfo.csv not found in the downloaded ZIP.")

                csv_filename = csv_files[0]
                dest_dir.mkdir(parents=True, exist_ok=True)
                z.extract(csv_filename, path=dest_dir)

                csv_path = dest_dir / csv_filename
                logger.info(f"Successfully extracted EDINET master CSV to {csv_path}")
                return csv_path

        except Exception as e:
            logger.error(f"Failed to download/extract EDINET master CSV: {e}")
            raise RuntimeError("Could not retrieve EDINET code master.") from e
