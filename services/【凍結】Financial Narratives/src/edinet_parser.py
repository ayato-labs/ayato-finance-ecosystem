import io
import re
import sys
import zipfile

from bs4 import BeautifulSoup
from loguru import logger
from markdownify import markdownify as md

# Increase recursion depth for deep iXBRL HTML structures
sys.setrecursionlimit(10000)


class EdinetParser:
    """
    Parser for Japanese EDINET documents (Yuho/Quarterly reports).
    Supports extraction from Inline XBRL (iXBRL) which is essentially HTML.
    """

    def __init__(self):
        pass

    def clean_text(self, text: str) -> str:
        if not text:
            return ""
        # Remove extra whitespace and normalized newlines
        lines = [line.strip() for line in text.split("\n")]
        cleaned_text = "\n".join(lines)
        cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)
        return cleaned_text.strip()

    def parse_zip(self, zip_bytes: bytes) -> dict[str, str]:
        """
        Extract and parse sections from an EDINET XBRL ZIP file.
        The zip contains a 'PublicDoc' folder with Inline XBRL (HTML) files.
        """
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
                # Inline XBRL documents are usually in PublicDoc/*.htm
                html_files = [
                    f for f in z.namelist() if "PublicDoc/" in f and f.endswith((".htm", ".html"))
                ]

                combined_results = {}
                for html_file in html_files:
                    with z.open(html_file) as f:
                        content = f.read().decode("utf-8", errors="ignore")
                        sections = self.parse_ixbrl(content)
                        # Merge results
                        for k, v in sections.items():
                            if v:
                                if k in combined_results:
                                    combined_results[k] += "\n\n" + v
                                else:
                                    combined_results[k] = v
                return combined_results
        except zipfile.BadZipFile:
            logger.error("Failed to parse EDINET ZIP: File is not a zip file or is corrupted")
            return {}
        except Exception:
            logger.exception("Unexpected error parsing EDINET ZIP")
            return {}

    def parse_ixbrl(self, html_content: str) -> dict[str, str]:
        """
        Ultra-fast extraction: Split by regex first, then parse fragments.
        Avoids BeautifulSoup recursion depth issues on 10MB+ documents.
        """
        results = {}

        # 1. まずは ix:nonNumeric タグのブロックをすべて抜き出す (属性の順序に依存しない)
        tag_pattern = re.compile(r"<(ix:nonNumeric)[^>]*>(.*?)</\1>", re.DOTALL | re.IGNORECASE)

        # 2. 抜き出したタグの中から name 属性を抽出する (シングル/ダブルクォート両対応)
        name_pattern = re.compile(r'name\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)

        match_count = 0
        for match in tag_pattern.finditer(html_content):
            match_count += 1
            opening_tag = match.group(0).split(">")[0]
            content = match.group(2)

            name_match = name_pattern.search(opening_tag)
            if not name_match:
                continue

            key = name_match.group(1)

            try:
                # フラグメントをパース
                fragment_soup = BeautifulSoup(content, "html.parser")

                # 1. 第一志望: マークダウン化 (RecursionError を警戒)
                try:
                    text = md(
                        str(fragment_soup),
                        heading_style="ATX",
                        bullets="-",
                        strip=["script", "style", "head"],
                        table_conversion="github",
                    )
                except (RecursionError, Exception) as e:
                    logger.warning(
                        f"Markdown conversion failed (Recursion/Error), falling back to text: {str(e)[:100]}"
                    )
                    # 2. フォールバック: 生テキスト
                    text = fragment_soup.get_text(separator="\n", strip=True)
            except Exception:
                # 3. 最終手段: タグ除去
                text = re.sub(r"<[^>]+>", "", content)

            cleaned_text = self.clean_text(text)
            if cleaned_text:
                if key in results:
                    results[key] += "\n\n" + cleaned_text
                else:
                    results[key] = cleaned_text

        if match_count > 0:
            logger.debug(f"Found {match_count} ix:nonNumeric blocks in HTML fragment")

        return results


if __name__ == "__main__":
    # Test with a dummy string
    parser = EdinetParser()
    dummy_html = (
        '<ix:nonNumeric name="jpcrp_cor:ResearchAndDevelopmentActivitiesTextBlock">'
        "Test R&D content</ix:nonNumeric>"
    )
    result = parser.parse_ixbrl(dummy_html)
    print(f"Test Result: {result}")
