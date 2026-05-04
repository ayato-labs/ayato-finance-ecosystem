import json
from pathlib import Path

import duckdb


def extract_samples():
    db_path = "data/financial_narratives.duckdb"
    output_dir = Path("artifacts/samples")
    output_dir.mkdir(parents=True, exist_ok=True)

    with duckdb.connect(db_path, read_only=True) as conn:
        # US Sample (e.g., AAPL)
        us_sample = conn.execute(
            """
            SELECT ticker, form, filing_date, sections, metadata
            FROM filings
            WHERE ticker = 'AAPL'
            ORDER BY filing_date DESC LIMIT 1
            """
        ).fetchone()

        # JP Sample (e.g., numeric ticker)
        jp_sample = conn.execute(
            """
            SELECT ticker, form, filing_date, sections, metadata
            FROM filings
            WHERE ticker ~ '^[0-9]+$'
            ORDER BY filing_date DESC LIMIT 1
            """
        ).fetchone()

        for sample in [us_sample, jp_sample]:
            if not sample:
                continue

            ticker, form, f_date, sections_json, _ = sample
            sections = json.loads(sections_json)

            md_content = [
                f"# Financial Narrative Sample: {ticker} ({form})",
                f"\n- **Filing Date**: {f_date}",
                f"- **Ticker/Code**: {ticker}",
                f"- **Form Type**: {form}",
                "\n---",
            ]

            for section_name, text in sections.items():
                md_content.append(f"\n## Section: {section_name}")
                md_content.append(f"\n{text}")
                md_content.append("\n---")

            filename = f"{ticker}_{form}_{f_date}.md"
            with open(output_dir / filename, "w", encoding="utf-8") as f:
                f.write("\n".join(md_content))

            print(f"Generated sample: {output_dir / filename}")


if __name__ == "__main__":
    extract_samples()
