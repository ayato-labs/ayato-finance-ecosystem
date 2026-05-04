import io
import re
import zipfile

from bs4 import BeautifulSoup
from loguru import logger
from markdownify import markdownify as md


class EdinetParser:
    """
    Parser for Japanese EDINET documents (Yuho/Quarterly reports).
    Supports extraction from Inline XBRL (iXBRL) which is essentially HTML.
    """

    # Mapping of sections to XBRL Tag patterns or header names
    # Note: EDINET uses standardized tags in jpcrp_cor namespace
    TAG_MAP = {
        "business_strategy": "jpcrp_cor:BusinessPoliciesBusinessEnvironmentAndIssuesToAddressTextBlock",
        "mda": "jpcrp_cor:AnalysisOfFinancialPositionOperatingResultsAndCashFlowsTextBlock",
        "risk_factors": "jpcrp_cor:BusinessRisksTextBlock",
        "rd": "jpcrp_cor:ResearchAndDevelopmentActivitiesTextBlock",
        "capex": "jpcrp_cor:FacilitiesChangesAndPlansTextBlock",
        "governance": "jpcrp_cor:CorporateGovernanceSummaryTextBlock",
    }

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
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            # Inline XBRL documents are usually in PublicDoc/*.htm
            # We look for the main document.
            # In Yuho, it's often the one starting with 'jpcrp' or similar.
            html_files = [
                f
                for f in z.namelist()
                if f.startswith("PublicDoc/") and f.endswith((".htm", ".html"))
            ]

            combined_results = {}
            for html_file in html_files:
                with z.open(html_file) as f:
                    content = f.read().decode("utf-8", errors="ignore")
                    sections = self.parse_ixbrl(content)
                    # Merge results (some sections might be split across files, though rare in Yuho)
                    for k, v in sections.items():
                        if v:
                            if k in combined_results:
                                combined_results[k] += "\n\n" + v
                            else:
                                combined_results[k] = v
            return combined_results

    def parse_ixbrl(self, html_content: str) -> dict[str, str]:
        """
        Extract sections from Inline XBRL (HTML) using Beautiful Soup.
        """
        soup = BeautifulSoup(html_content, "lxml")
        results = {}

        for key, tag_name in self.TAG_MAP.items():
            # EDINET uses <ix:nonNumeric name="jpcrp_cor:..." ...>
            # Beautiful Soup handles ix: tags if using lxml or html.parser
            # However, sometimes they are namespaced like <ix:nonNumeric name="jpcrp_cor:ResearchAndDevelopmentActivitiesTextBlock">
            element = soup.find(lambda t: t.get("name") == tag_name)

            if element:
                # Convert to markdown
                markdown_content = md(
                    str(element),
                    heading_style="ATX",
                    bullets="-",
                    strip=["script", "style", "head"],
                    table_conversion="github",
                )
                results[key] = self.clean_text(markdown_content)
                logger.info(f"Extracted JP section: {key} (size: {len(results[key])})")

        return results

    def extract_from_html(self, html_content: str) -> dict[str, str]:
        """Generic extraction for non-XBRL HTML (PDF-to-HTML) based on headers."""
        # This is a fallback if XBRL tags are missing
        # For now, we prioritize XBRL
        return self.parse_ixbrl(html_content)


if __name__ == "__main__":
    # Test with a dummy string
    parser = EdinetParser()
    dummy_html = '<ix:nonnumeric name="jpcrp_cor:ResearchAndDevelopmentActivitiesTextBlock">Test R&D content</ix:nonnumeric>'
    print(parser.parse_ixbrl(dummy_html))
