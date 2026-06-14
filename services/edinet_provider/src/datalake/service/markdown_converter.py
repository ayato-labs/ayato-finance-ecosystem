import re
import warnings
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning, NavigableString, Tag
from loguru import logger

# Filter BeautifulSoup warnings about text looking like URLs
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)


def clean_html_to_markdown(html_content: str) -> str:
    """
    HTML content extracted from EDINET XBRL to a clean Markdown format.
    Handles headings, paragraphs, breaks, bold/italic, and tables.
    """
    if not html_content or not isinstance(html_content, str):
        return ""

    try:
        # Parse HTML using BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")

        # Remove scripts, styles, and other noise
        for element in soup(["script", "style", "head", "title", "meta", "link"]):
            element.decompose()

        # Parse tags recursively
        markdown_text = _parse_element(soup)

        # Post-processing: clean up excessive line breaks and whitespace
        # 1. Replace 3 or more consecutive newlines with exactly two newlines
        markdown_text = re.sub(r"\n{3,}", "\n\n", markdown_text)
        # 2. Trim whitespace on each line but keep structure
        lines = [line.rstrip() for line in markdown_text.split("\n")]
        markdown_text = "\n".join(lines)
        # 3. Strip leading/trailing newlines of the whole text
        return markdown_text.strip()

    except Exception as e:
        logger.error(f"Failed to convert HTML to Markdown: {e}")
        # Return fallback plain text on error
        return re.sub(r"<[^>]+>", "", html_content).strip()


def _parse_element(element) -> str:
    """
    Helper to recursively parse HTML elements to Markdown.
    """
    if isinstance(element, NavigableString):
        # Clean up string but preserve single spaces/newlines
        text = str(element)
        # Replace multiple spaces with a single space, but keep line breaks intact
        text = re.sub(r"[ \t]+", " ", text)
        return text

    if not isinstance(element, Tag):
        return ""

    result = []

    # Handle tags
    tag_name = element.name.lower()

    if tag_name == "br":
        return "\n"

    # Pre-child formatting
    if tag_name in ["p", "div"]:
        result.append("\n")
    elif tag_name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
        level = int(tag_name[1])
        result.append(f"\n\n{'#' * level} ")

    # Parse children recursively
    child_texts = []
    for child in element.children:
        child_texts.append(_parse_element(child))
    inner_text = "".join(child_texts)

    # Post-child formatting / Wrapping
    if tag_name in ["strong", "b"]:
        inner_text = inner_text.strip()
        if inner_text:
            result.append(f"**{inner_text}**")
    elif tag_name in ["em", "i"]:
        inner_text = inner_text.strip()
        if inner_text:
            result.append(f"*{inner_text}*")
    elif tag_name in ["p", "div"]:
        result.append(inner_text)
        result.append("\n")
    elif tag_name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
        result.append(inner_text.strip())
        result.append("\n\n")
    elif tag_name == "table":
        # Render table separately
        table_md = _render_table(element)
        result.append(f"\n\n{table_md}\n\n")
    elif tag_name in ["tr", "th", "td", "thead", "tbody"]:
        # These are handled inside _render_table, so we ignore them here to avoid duplication
        pass
    else:
        # Default tag container, just pass through inner text
        result.append(inner_text)

    return "".join(result)


def _render_table(table_tag: Tag) -> str:
    """
    Renders an HTML table element into Markdown table format.
    """
    rows = table_tag.find_all("tr")
    if not rows:
        return ""

    markdown_rows = []
    col_count = 0

    # Determine table structure and normalize cells
    for r_idx, row in enumerate(rows):
        cells = row.find_all(["th", "td"])
        if not cells:
            continue

        # Get values and strip formatting
        cell_vals = []
        for cell in cells:
            # Render cell children to markdown to avoid the th/td skip rule
            child_texts = []
            for child in cell.children:
                child_texts.append(_parse_element(child))
            val = "".join(child_texts).strip()
            # Clean up newlines inside cells to avoid breaking MD table structure
            val = val.replace("\n", " ").replace("|", "\\|")
            cell_vals.append(val)

        if not cell_vals:
            continue

        col_count = max(col_count, len(cell_vals))
        markdown_rows.append(cell_vals)

    if not markdown_rows:
        return ""

    # Build the Markdown table
    table_lines = []

    # 1. Header Row
    header_row = markdown_rows[0]
    # Pad header row to col_count if it's shorter
    header_row += [""] * (col_count - len(header_row))
    table_lines.append("| " + " | ".join(header_row) + " |")

    # 2. Separator Row
    separator = "| " + " | ".join(["---"] * col_count) + " |"
    table_lines.append(separator)

    # 3. Data Rows
    for row in markdown_rows[1:]:
        row += [""] * (col_count - len(row))
        table_lines.append("| " + " | ".join(row) + " |")

    return "\n".join(table_lines)
