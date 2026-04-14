"""PDF 表格提取模块。

负责从 PDF 页面中提取表格，支持几何检测（PyMuPDF find_tables）与
纯文本模式匹配两种策略，并将结果统一封装为 ``ExtractedTable`` 数据类。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..figure_text_filter import CAPTION_PATTERNS as _CAPTION_PATTERNS
from ._shared import generate_asset_id

# PyMuPDF imports for PDF processing
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------


@dataclass
class ExtractedTable:
    """Data class for extracted table information."""

    id: str
    markdown: str
    rows: int
    columns: int
    page_number: Optional[int] = None
    position: Optional[Dict[str, float]] = None
    caption: Optional[str] = None
    headers: Optional[List[str]] = None
    bbox: Optional[Tuple[float, float, float, float]] = None  # (x0, y0, x1, y1)


# ---------------------------------------------------------------------------
# 表格标题检测
# ---------------------------------------------------------------------------


def detect_table_caption(
    text_blocks: list,
    table_bbox: Tuple[float, float, float, float],
    tolerance: float = 30.0,
) -> Optional[str]:
    """Detect caption text near a table (above or below).

    Checks both above and below the table bounding box because table
    captions can appear in either position.

    Args:
        text_blocks: Text-only blocks (block[6] == 0)
        table_bbox: (x0, y0, x1, y1) of the table
        tolerance: Max vertical distance to search

    Returns:
        Caption string if found, else None
    """
    tx0, ty0, tx1, ty1 = table_bbox
    best_caption = None
    best_distance = tolerance + 1

    for block in text_blocks:
        if block[6] != 0:
            continue
        block_text = block[4].strip() if block[4] else ""
        if not block_text:
            continue

        block_y0, block_y1 = block[1], block[3]
        block_x0, block_x1 = block[0], block[2]

        # Check horizontal overlap
        overlap = min(block_x1, tx1) - max(block_x0, tx0)
        if overlap <= 0:
            continue

        # Check above table (caption like "Table 9: ...")
        dist_above = ty0 - block_y1
        # Check below table
        dist_below = block_y0 - ty1

        distance = min(
            dist_above if dist_above >= -5 else tolerance + 1,
            dist_below if dist_below >= -5 else tolerance + 1,
        )

        if distance > tolerance:
            continue

        first_line = block_text.split("\n")[0].strip()
        for pattern in _CAPTION_PATTERNS:
            if pattern.match(first_line):
                if distance < best_distance:
                    best_distance = distance
                    best_caption = re.sub(r"\n+", " ", block_text).strip()
                    if len(best_caption) > 120:
                        best_caption = best_caption[:120]
                break

    return best_caption


# ---------------------------------------------------------------------------
# 几何表格提取（PyMuPDF find_tables）
# ---------------------------------------------------------------------------


def extract_tables_with_geometry(
    pdf_document,
    page_num: int,
    text_blocks: list,
) -> Tuple[
    Dict[Tuple[float, float, float, float], ExtractedTable],
    List[ExtractedTable],
]:
    """Extract tables using PyMuPDF's geometric table detection.

    Uses a two-phase approach:
    1. Detect table title positions ("Table N:") to create clip regions
    2. Run page.find_tables() on each clip region for precise extraction
    3. Post-process: merge continuation columns/rows, clean cell text

    Falls back to full-page detection when no table titles are found.

    Args:
        pdf_document: PyMuPDF document object
        page_num: Page number (0-indexed)
        text_blocks: All blocks from page.get_text("blocks")

    Returns:
        Tuple of:
        - Dict mapping table bbox -> ExtractedTable (for inline placement)
        - List of all ExtractedTable objects
    """
    bbox_to_table: Dict[Tuple[float, float, float, float], ExtractedTable] = {}
    all_tables: List[ExtractedTable] = []

    try:
        if fitz is None:
            raise ImportError("PyMuPDF (fitz) is not available")

        page = pdf_document[page_num]
        text_only_blocks = [b for b in text_blocks if b[6] == 0]
        page_rect = page.rect

        # Phase 1: Detect table title positions for clip-based extraction
        title_regions = _find_table_title_regions(
            page,
            text_only_blocks,
            page_rect,
        )

        if title_regions:
            # Extract each table using its clip region
            for table_idx, (title, clip_rect, title_rect) in enumerate(title_regions):
                table = _extract_single_table(
                    page,
                    clip_rect,
                    title,
                    title_rect,
                    text_only_blocks,
                    page_num,
                    table_idx,
                )
                if table:
                    bbox_to_table[table.bbox] = table  # type: ignore[index]
                    all_tables.append(table)
        else:
            # Phase 2: Full-page fallback with both strategies
            found_tables = _find_tables_fullpage(page)

            for table_idx, table in enumerate(found_tables):
                extracted = _process_found_table(
                    table,
                    text_only_blocks,
                    page_num,
                    table_idx,
                )
                if extracted:
                    bbox_to_table[extracted.bbox] = extracted  # type: ignore[index]
                    all_tables.append(extracted)

    except ImportError:
        logger.error("PyMuPDF (fitz) is required for geometric table extraction")
    except Exception as e:
        logger.error(f"Error in geometric table extraction for page {page_num}: {e}")

    return bbox_to_table, all_tables


def _find_table_title_regions(
    page,
    text_blocks: list,
    page_rect,
) -> List[Tuple[str, Any, Any]]:
    """Find table titles and compute clip rectangles for each table.

    Returns list of (title_text, clip_rect, title_rect) tuples.
    """
    table_title_pattern = re.compile(r"^(Table|表)\s*\d+", re.IGNORECASE)

    # Collect title positions
    titles = []
    for block in sorted(text_blocks, key=lambda b: b[1]):
        if block[6] != 0:
            continue
        text = block[4].strip() if block[4] else ""
        first_line = text.split("\n")[0].strip()
        if table_title_pattern.match(first_line):
            title_text = re.sub(r"\n+", " ", text).strip()
            if len(title_text) > 120:
                title_text = title_text[:120]
            title_rect = fitz.Rect(block[0], block[1], block[2], block[3])
            titles.append((title_text, title_rect))

    if not titles:
        return []

    # Create clip regions: from title bottom to next title top (or page bottom)
    regions = []
    margin_x = 20
    for i, (title_text, title_rect) in enumerate(titles):
        clip_top = title_rect.y1 + 2
        if i + 1 < len(titles):
            clip_bottom = titles[i + 1][1].y0 - 5
        else:
            clip_bottom = page_rect.height - 40

        clip = fitz.Rect(
            max(page_rect.x0, title_rect.x0 - margin_x),
            clip_top,
            min(page_rect.x1, page_rect.x1 - margin_x),
            clip_bottom,
        )
        regions.append((title_text, clip, title_rect))

    return regions


def _extract_single_table(
    page,
    clip_rect,
    title: str,
    title_rect,
    text_blocks: list,
    page_num: int,
    table_idx: int,
) -> Optional[ExtractedTable]:
    """Extract a single table from a clipped page region."""
    try:
        # Try text strategy (works for borderless tables)
        tabs = page.find_tables(clip=clip_rect, strategy="text")
        found = list(tabs.tables) if tabs else []

        # Fallback to lines strategy
        if not found:
            tabs = page.find_tables(clip=clip_rect)
            found = list(tabs.tables) if tabs else []

        if not found:
            return None

        table = found[0]  # Use the first/largest table in the clip
        if table.row_count < 2 or table.col_count < 2:
            return None

        extracted_data = table.extract()
        if not extracted_data:
            return None

        # Post-process: merge continuation columns and rows
        merged_data = merge_table_columns_and_rows(extracted_data)
        if not merged_data or len(merged_data) < 2:
            return None

        # Build markdown from merged data
        markdown_str = build_markdown_from_data(merged_data)
        if not markdown_str:
            return None

        # Use the title region + table body as the overall bbox
        bbox = (
            clip_rect.x0,
            title_rect.y0,
            clip_rect.x1,
            min(float(table.bbox[3]) + 5, float(clip_rect.y1)),
        )

        table_id = generate_asset_id("table", page_num, table_idx)

        return ExtractedTable(
            id=table_id,
            markdown=markdown_str,
            rows=len(merged_data) - 1,  # Exclude header
            columns=len(merged_data[0]),
            page_number=page_num,
            position={
                "x0": bbox[0],
                "y0": bbox[1],
                "x1": bbox[2],
                "y1": bbox[3],
            },
            caption=title,
            headers=merged_data[0] if merged_data else None,
            bbox=bbox,
        )

    except Exception as e:
        logger.warning(f"Failed to extract table '{title}' on page {page_num}: {e}")
        return None


def _find_tables_fullpage(page) -> list:
    """Find tables on a full page using both strategies."""
    # Try lines first
    tabs = page.find_tables()
    found = list(tabs.tables) if tabs else []
    if found:
        return found

    # Fallback to text strategy
    try:
        tabs = page.find_tables(strategy="text")
        return list(tabs.tables) if tabs else []
    except Exception:
        return []


def _process_found_table(
    table,
    text_blocks: list,
    page_num: int,
    table_idx: int,
) -> Optional[ExtractedTable]:
    """Process a single found table into an ExtractedTable."""
    try:
        if table.row_count < 2 or table.col_count < 2:
            return None

        extracted_data = table.extract()
        if not extracted_data:
            return None

        # Post-process if there are empty header columns
        merged_data = merge_table_columns_and_rows(extracted_data)
        if not merged_data or len(merged_data) < 2:
            return None

        markdown_str = build_markdown_from_data(merged_data)
        if not markdown_str:
            return None

        bbox = tuple(table.bbox)

        caption = detect_table_caption(text_blocks, bbox, tolerance=30.0)

        table_id = generate_asset_id("table", page_num, table_idx)

        return ExtractedTable(
            id=table_id,
            markdown=markdown_str,
            rows=len(merged_data) - 1,
            columns=len(merged_data[0]),
            page_number=page_num,
            position={
                "x0": bbox[0],
                "y0": bbox[1],
                "x1": bbox[2],
                "y1": bbox[3],
            },
            caption=caption,
            headers=merged_data[0] if merged_data else None,
            bbox=bbox,
        )

    except Exception as e:
        logger.warning(f"Failed to process table {table_idx} on page {page_num}: {e}")
        return None


# ---------------------------------------------------------------------------
# 表格后处理
# ---------------------------------------------------------------------------


def merge_table_columns_and_rows(
    data: List[List[Optional[str]]],
) -> List[List[str]]:
    """Merge continuation columns (empty headers) and continuation rows.

    Handles two common PDF table extraction artifacts:
    1. Extra columns where the header cell is empty (text overflow)
    2. Continuation rows where leading cells are empty (wrapped text)
    """
    if not data:
        return []

    header = data[0]

    # Find columns with non-empty headers
    content_cols = [i for i, h in enumerate(header) if h and h.strip()]

    # If all headers are populated, no column merging needed
    if len(content_cols) == len(header):
        content_cols = list(range(len(header)))

    if not content_cols:
        return []

    # Merge columns based on content column boundaries
    merged_rows = []
    for row in data:
        merged = []
        for ci, col_idx in enumerate(content_cols):
            next_col = (
                content_cols[ci + 1] if ci + 1 < len(content_cols) else len(header)
            )
            parts = []
            for j in range(col_idx, next_col):
                cell = row[j] if j < len(row) and row[j] else ""
                # Clean up <br> tags from PyMuPDF
                cell = re.sub(r"<br>\s*", " ", cell).strip()  # type: ignore[arg-type]
                if cell:
                    parts.append(cell)
            merged.append(" ".join(parts))
        merged_rows.append(merged)

    # Merge continuation rows (leading cells empty = wrapped text)
    final_rows: List[List[str]] = []
    for row in merged_rows:  # type: ignore[assignment]
        if row[0].strip():  # type: ignore[union-attr]  # New data row
            # Clean hyphen-broken words in each cell
            final_rows.append([re.sub(r"(\w)- (\w)", r"\1\2", c) for c in row])  # type: ignore[arg-type]
        elif final_rows:  # Continuation row
            for ci in range(len(row)):
                if row[ci].strip():  # type: ignore[union-attr]
                    text = re.sub(r"(\w)- (\w)", r"\1\2", row[ci])  # type: ignore[arg-type]
                    sep = " " if final_rows[-1][ci] else ""
                    final_rows[-1][ci] += sep + text

    return final_rows


def build_markdown_from_data(data: List[List[str]]) -> str:
    """Build a GFM markdown table from processed cell data."""
    if not data or len(data) < 2:
        return ""

    num_cols = len(data[0])
    lines = []

    # Header
    lines.append("| " + " | ".join(data[0]) + " |")
    # Separator
    lines.append("| " + " | ".join(["---"] * num_cols) + " |")
    # Data rows
    for row in data[1:]:
        # Pad/trim to match column count
        padded = row[:num_cols] + [""] * max(0, num_cols - len(row))
        # Escape pipe chars in cell content
        escaped = [c.replace("|", "\\|") for c in padded]
        lines.append("| " + " | ".join(escaped) + " |")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 纯文本表格提取
# ---------------------------------------------------------------------------


def extract_tables_from_text(text: str, page_num: int) -> List[ExtractedTable]:
    """Extract tables from plain text using pattern recognition.

    Args:
        text: Text content from PDF page
        page_num: Page number

    Returns:
        List of ExtractedTable objects
    """
    tables: List[ExtractedTable] = []

    try:
        # Split text into lines
        lines = text.split("\n")

        # Look for table patterns
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Check if this looks like a table row (contains multiple separators)
            if is_table_row(line):
                table_lines = []

                # Collect consecutive table rows
                while i < len(lines) and is_table_row(lines[i].strip()):
                    table_lines.append(lines[i].strip())
                    i += 1

                # Convert to Markdown table
                if len(table_lines) >= 2:  # At least header and one data row
                    table_id = generate_asset_id("table", page_num, len(tables))
                    markdown_table = convert_to_markdown_table(table_lines)

                    if markdown_table:
                        # Calculate actual rows and columns
                        if "|" in table_lines[0]:
                            columns = len(
                                [
                                    cell.strip()
                                    for cell in table_lines[0].split("|")
                                    if cell.strip()
                                ]
                            )
                            # Count the number of actual data rows (non-separator)
                            data_rows = len(
                                [
                                    line
                                    for line in table_lines
                                    if not re.match(r"^[\s\|\-]+$", line.strip())
                                ]
                            )
                            # Count actual content rows (exclude markdown separator)
                            total_rows = data_rows
                        else:
                            columns = len(table_lines[0].split("\t"))
                            total_rows = len(table_lines)

                        extracted_table = ExtractedTable(
                            id=table_id,
                            markdown=markdown_table,
                            rows=total_rows,
                            columns=columns,
                            page_number=page_num,
                            headers=extract_table_headers(table_lines[0])
                            if table_lines
                            else None,
                        )

                        tables.append(extracted_table)
                        logger.info(f"Extracted table {table_id} from page {page_num}")

            i += 1

    except Exception as e:
        logger.error(f"Error extracting tables from page {page_num}: {str(e)}")

    return tables


# ---------------------------------------------------------------------------
# 辅助判断函数
# ---------------------------------------------------------------------------


def is_table_row(line: str) -> bool:
    """Check if a line looks like a table row."""
    line_stripped = line.strip()

    # Check for tab-separated or pipe-separated values
    tab_count = line_stripped.count("\t")
    pipe_count = line_stripped.count("|")

    # Multiple separators suggest a table row
    # For tabs: need at least 2 tabs (3 columns)
    # For pipes: need at least 2 pipes (3 columns if properly formatted)
    if tab_count >= 2 or pipe_count >= 2:
        return True

    # For space-separated, check for multiple spaces in original line
    return _has_multiple_space_separators(line_stripped)


def _has_multiple_space_separators(line: str) -> bool:
    """Check if a line has multiple space separators (more than 2 spaces between words)."""
    return bool(re.search(r" {2,}", line)) and len(line.split()) >= 3


def convert_to_markdown_table(table_lines: List[str]) -> str:
    """Convert table lines to Markdown format."""
    if not table_lines:
        return ""

    try:
        # Determine separator type
        first_line = table_lines[0]

        if "|" in first_line:
            # Pipe-separated table
            rows = []
            for line in table_lines:
                # Check if this is already a separator line (contains only dashes and pipes)
                if re.match(r"^[\s\|\-]+$", line.strip()):
                    continue  # Skip existing separator lines

                # Clean up pipe separators
                cleaned = (
                    "| "
                    + " | ".join(
                        [cell.strip() for cell in line.split("|") if cell.strip()]
                    )
                    + " |"
                )
                rows.append(cleaned)

            # Add header separator after first row
            if len(rows) >= 2:
                header_cols = len(rows[0].split("|")) - 2
                separator = "| " + " | ".join(["---"] * header_cols) + " |"
                rows.insert(1, separator)

            return "\n".join(rows)

        elif "\t" in first_line:
            # Tab-separated table - convert to pipe
            rows = []
            for line in table_lines:
                cells = [cell.strip() for cell in line.split("\t")]
                markdown_row = "| " + " | ".join(cells) + " |"
                rows.append(markdown_row)

            # Add header separator
            if len(rows) >= 2:
                header_cols = len(rows[0].split("|")) - 2
                separator = "| " + " | ".join(["---"] * header_cols) + " |"
                rows.insert(1, separator)

            return "\n".join(rows)
        else:
            # Space-separated table
            rows = []
            for line in table_lines:
                # Split by multiple spaces
                cells = re.split(r"\s{2,}", line.strip())
                if len(cells) > 1:
                    markdown_row = "| " + " | ".join(cells) + " |"
                    rows.append(markdown_row)

            # Add header separator
            if len(rows) >= 2:
                header_cols = len(rows[0].split("|")) - 2
                separator = "| " + " | ".join(["---"] * header_cols) + " |"
                rows.insert(1, separator)

            return "\n".join(rows)

    except Exception as e:
        logger.error(f"Error converting table to Markdown: {str(e)}")
        return ""


def extract_table_headers(header_line: str) -> List[str]:
    """Extract headers from table header line."""
    try:
        if "|" in header_line:
            return [cell.strip() for cell in header_line.split("|") if cell.strip()]
        elif "\t" in header_line:
            return [cell.strip() for cell in header_line.split("\t")]
        else:
            return re.split(r"\s{2,}", header_line.strip())
    except Exception:
        return []
