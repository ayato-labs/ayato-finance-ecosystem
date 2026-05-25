import io
import os
import zipfile
from datetime import date
from typing import Any

import pandas as pd
import requests
from loguru import logger


class EdinetFetcher:
    """
    Financial Services Agency EDINET API v2 Fetcher

    References:
    - EDINET API 仕様書 (Version 2)
    - Documents List API: /api/v2/documents.json
    - Documents Get API: /api/v2/documents/{docID}
    """

    BASE_URL = "https://api.edinet-fsa.go.jp/api/v2"
    CODE_LIST_URL = "https://disclosure2dl.edinet-fsa.go.jp/searchdocument/codelist/Edinetcode.zip"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("EDINET_API_KEY")
        if not self.api_key:
            logger.warning("EDINET_API_KEY is not set. API calls may fail.")

        self.code_map: pd.DataFrame | None = None
        self._data_dir = os.path.join(os.getcwd(), "data", "edinet")
        os.makedirs(self._data_dir, exist_ok=True)

    def _ensure_code_map(self):
        """Load or download EDINET code list mapping."""
        try:
            cache_path = os.path.join(self._data_dir, "Edinetcode.csv")

            if os.path.exists(cache_path):
                # Load from cache
                self.code_map = pd.read_csv(cache_path, encoding="cp932", skiprows=1)
                return

            logger.info("Downloading EDINET code list")
            response = requests.get(self.CODE_LIST_URL, timeout=30)
            if response.status_code == 200:
                with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                    for filename in z.namelist():
                        if filename.endswith(".csv"):
                            with z.open(filename) as f:
                                content = f.read()
                                with open(cache_path, "wb") as out:
                                    out.write(content)
                                self.code_map = pd.read_csv(
                                    io.BytesIO(content), encoding="cp932", skiprows=1
                                )
                                logger.info(
                                    f"EDINET code list cached | entries={len(self.code_map)}"
                                )
                                return
            else:
                logger.error(f"Failed to download EDINET code list | status={response.status_code}")
        except Exception:
            logger.exception("Failed to ensure EDINET code map")

    def get_all_listed_tickers(self) -> list[str]:
        """全上場企業の証券コードリストを取得"""
        try:
            if self.code_map is None:
                self._ensure_code_map()
            if self.code_map is None:
                return []
            codes = self.code_map["証券コード"].dropna().astype(str).tolist()
            return [c[:4] for c in codes if len(c) >= 4 and c[0].isdigit()]
        except Exception:
            logger.exception("Error getting all listed tickers")
            return []

    def get_edinet_code(self, ticker: str) -> str | None:
        """Map 4-digit Securities Code to EDINET Code (E+5 digits)."""
        try:
            if self.code_map is None:
                self._ensure_code_map()
            if self.code_map is None:
                return None
            matches = self.code_map[self.code_map["証券コード"].astype(str).str.startswith(ticker)]
            if not matches.empty:
                return matches.iloc[0]["ＥＤＩＮＥＴコード"]
            return None
        except Exception:
            logger.exception(f"Error mapping ticker to EDINET code | ticker={ticker}")
            return None

    def list_documents(self, target_date: date, list_type: int = 2) -> list[dict[str, Any]]:
        """List documents for a specific date."""
        try:
            url = f"{self.BASE_URL}/documents.json"
            params = {
                "date": target_date.strftime("%Y-%m-%d"),
                "type": list_type,
            }
            headers = {"Ocp-Apim-Subscription-Key": self.api_key}

            logger.info(f"Listing EDINET documents | date={target_date}")
            response = requests.get(url, params=params, headers=headers, timeout=15)

            if response.status_code == 200:
                data = response.json()
                if "results" in data:
                    return data.get("results", [])

                metadata = data.get("metadata", {})
                status = metadata.get("status")
                message = metadata.get("message")
                logger.error(f"EDINET API error in metadata | status={status} | message={message}")
                if status == "403":
                    logger.error("403 Forbidden: Check if your EDINET_API_KEY is valid.")
            else:
                logger.error(
                    f"EDINET request failed | status={response.status_code} | body={response.text[:200]}"
                )
        except Exception:
            logger.exception(f"Exception during EDINET document listing | date={target_date}")

        return []

    def download_document(self, doc_id: str, doc_type: int = 1) -> bytes | None:
        """Download a specific document."""
        try:
            url = f"{self.BASE_URL}/documents/{doc_id}"
            params = {"type": doc_type, "Subscription-Key": self.api_key}
            headers = {"Ocp-Apim-Subscription-Key": self.api_key}

            logger.info(f"Downloading EDINET document | doc_id={doc_id} | type={doc_type}")
            response = requests.get(url, params=params, headers=headers, timeout=60)

            if response.status_code == 200:
                content_type = response.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    error_data = response.json()
                    logger.error(
                        f"EDINET download error in body | doc_id={doc_id} | error={error_data}"
                    )
                    return None
                return response.content
            else:
                logger.error(
                    f"EDINET download failed | doc_id={doc_id} | status={response.status_code}"
                )
        except Exception:
            logger.exception(f"Exception during EDINET document download | doc_id={doc_id}")

        return None


if __name__ == "__main__":
    # Test mapping
    fetcher = EdinetFetcher()
    code = fetcher.get_edinet_code("7203")
    print(f"Toyota EDINET Code: {code}")  # Should be E02144
