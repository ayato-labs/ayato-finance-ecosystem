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
        cache_path = os.path.join(self._data_dir, "Edinetcode.csv")

        if os.path.exists(cache_path):
            # Load from cache
            self.code_map = pd.read_csv(cache_path, encoding="cp932", skiprows=1)
            return

        logger.info("Downloading EDINET code list...")
        response = requests.get(self.CODE_LIST_URL)
        if response.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                # The zip usually contains Edinetcode.csv
                for filename in z.namelist():
                    if filename.endswith(".csv"):
                        with z.open(filename) as f:
                            content = f.read()
                            # Save to cache
                            with open(cache_path, "wb") as out:
                                out.write(content)
                            self.code_map = pd.read_csv(
                                io.BytesIO(content), encoding="cp932", skiprows=1
                            )
                            logger.info(f"EDINET code list cached: {len(self.code_map)} entries")
                            return
        else:
            logger.error(f"Failed to download EDINET code list: {response.status_code}")

    def get_all_listed_tickers(self) -> list[str]:
        """全上場企業の証券コードリストを取得"""
        if self.code_map is None:
            self._ensure_code_map()

        if self.code_map is None:
            return []

        # '証券コード' 列から null 以外を取得。5桁(末尾0)なので4桁に変換
        # 実際には 72030.0 のような float になっている可能性があるので変換に注意
        codes = self.code_map["証券コード"].dropna().astype(str).tolist()
        # 末尾の0を除去して4桁にする
        return [c[:4] for c in codes if len(c) >= 4 and c[0].isdigit()]

    def get_edinet_code(self, ticker: str) -> str | None:
        """Map 4-digit Securities Code to EDINET Code (E+5 digits)."""
        if self.code_map is None:
            self._ensure_code_map()

        if self.code_map is None:
            return None

        # Securities code is in '証券コード' column (5 digits usually, includes trailing 0)
        # Ticker 7203 -> 72030 in the list
        ticker_search = f"{ticker}0"

        # '証券コード' might be float or string
        matches = self.code_map[self.code_map["証券コード"].astype(str).str.startswith(ticker)]
        if not matches.empty:
            return matches.iloc[0]["ＥＤＩＮＥＴコード"]

        return None

    def list_documents(self, target_date: date, list_type: int = 2) -> list[dict[str, Any]]:
        """
        List documents for a specific date.
        type: 1 (metadata only), 2 (metadata + document list)
        """
        url = f"{self.BASE_URL}/documents.json"
        params = {
            "date": target_date.strftime("%Y-%m-%d"),
            "type": list_type,
            "Subscription-Key": self.api_key,
        }

        logger.info(f"Listing EDINET documents for {target_date}...")
        try:
            response = requests.get(url, params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()
                metadata = data.get("metadata", {})
                status = metadata.get("status")
                if status == "200":
                    return data.get("results", [])
                
                message = metadata.get("message")
                logger.error(f"EDINET API Error: Status={status}, Message={message}")
                if status == "403":
                    logger.error("403 Forbidden: Check if your EDINET_API_KEY is valid.")
            else:
                logger.error(f"EDINET Request Failed: {response.status_code}")
        except Exception as e:
            logger.error(f"EDINET API Exception: {e}")

        return []

    def download_document(self, doc_id: str, doc_type: int = 1) -> bytes | None:
        """
        Download a specific document.
        type: 1 (XBRL), 2 (PDF), 5 (CSV)
        """
        url = f"{self.BASE_URL}/documents/{doc_id}"
        params = {"type": doc_type, "Subscription-Key": self.api_key}

        logger.info(f"Downloading EDINET document {doc_id} (type={doc_type})...")
        response = requests.get(url, params=params)

        if response.status_code == 200:
            # Check Content-Type (as per PDF spec p.84/89)
            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type:
                # Error message
                error_data = response.json()
                logger.error(f"EDINET Download Error: {error_data}")
                return None
            return response.content
        else:
            logger.error(f"EDINET Download Failed: {response.status_code}")

        return None


if __name__ == "__main__":
    # Test mapping
    fetcher = EdinetFetcher()
    code = fetcher.get_edinet_code("7203")
    print(f"Toyota EDINET Code: {code}")  # Should be E02144
