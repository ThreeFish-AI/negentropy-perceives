"""Enhanced PDF processing module for extracting images, tables, and mathematical formulas."""

import logging
import tempfile
import os
import re
import base64
import unicodedata
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from .figure_text_filter import CAPTION_PATTERNS as _CAPTION_PATTERNS

# PyMuPDF imports for PDF processing
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


@dataclass
class ExtractedImage:
    """Data class for extracted image information."""

    id: str
    filename: str
    local_path: str
    base64_data: Optional[str] = None
    mime_type: str = "image/png"
    width: Optional[int] = None
    height: Optional[int] = None
    page_number: Optional[int] = None
    position: Optional[Dict[str, float]] = None
    caption: Optional[str] = None
    xref: Optional[int] = None


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


@dataclass
class ExtractedFormula:
    """Data class for extracted mathematical formula."""

    id: str
    latex: str
    formula_type: str  # "inline" or "block"
    page_number: Optional[int] = None
    position: Optional[Dict[str, float]] = None
    description: Optional[str] = None


class EnhancedPDFProcessor:
    """Enhanced PDF processor with support for images, tables, and mathematical formulas."""

    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize the enhanced PDF processor.

        Args:
            output_dir: Directory to save extracted images and assets
        """
        self.logger = logging.getLogger(__name__)

        # Create output directory for extracted assets
        if output_dir:
            self.output_dir = Path(output_dir)
            self.output_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.output_dir = Path(tempfile.mkdtemp(prefix="enhanced_pdf_"))

        # Extracted content storage
        self.images: List[ExtractedImage] = []
        self.tables: List[ExtractedTable] = []
        self.formulas: List[ExtractedFormula] = []

        # Processing options
        self.extract_images = True
        self.extract_tables = True
        self.extract_formulas = True

    def _generate_asset_id(self, asset_type: str, page_num: int, index: int) -> str:
        """Generate unique ID for extracted assets (tables, formulas)."""
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{asset_type}_{page_num}_{index}_{timestamp}"

    @staticmethod
    def _slugify(text: str, max_length: int = 60) -> str:
        """Convert text to a filesystem-safe slug."""
        # Normalize unicode
        text = unicodedata.normalize("NFKD", text)
        # Keep only alphanumeric, spaces, hyphens, underscores, and CJK characters
        cleaned = []
        for ch in text:
            if ch.isalnum() or ch in (" ", "-", "_"):
                cleaned.append(ch)
            elif unicodedata.category(ch).startswith("Lo"):
                # Keep CJK and other letter characters
                cleaned.append(ch)
        slug = "".join(cleaned).strip()
        # Replace whitespace runs with hyphens
        slug = re.sub(r"[\s]+", "-", slug)
        # Collapse multiple hyphens
        slug = re.sub(r"-{2,}", "-", slug)
        # Truncate
        if len(slug) > max_length:
            slug = slug[:max_length].rstrip("-")
        return slug.lower() if slug else ""

    def _detect_caption(
        self,
        text_blocks: list,
        img_y1: float,
        img_x0: float,
        img_x1: float,
        tolerance: float = 30.0,
    ) -> Optional[str]:
        """Detect caption text below an image by scanning nearby text blocks.

        Args:
            text_blocks: All blocks from page.get_text("blocks"), filtered to type==0.
            img_y1: Bottom y-coordinate of the image.
            img_x0: Left x-coordinate of the image.
            img_x1: Right x-coordinate of the image.
            tolerance: Maximum vertical distance to consider a block as caption.

        Returns:
            Caption string if found, else None.
        """
        best_caption = None
        best_distance = tolerance + 1

        for block in text_blocks:
            if block[6] != 0:
                continue
            block_y0 = block[1]
            block_text = block[4].strip() if block[4] else ""
            if not block_text:
                continue

            # Block must be below the image and within tolerance
            vertical_distance = block_y0 - img_y1
            if vertical_distance < -5 or vertical_distance > tolerance:
                continue

            # Block should horizontally overlap with the image
            block_x0, block_x1 = block[0], block[2]
            overlap = min(block_x1, img_x1) - max(block_x0, img_x0)
            if overlap <= 0:
                continue

            # Check if text matches caption patterns
            first_line = block_text.split("\n")[0].strip()
            for pattern in _CAPTION_PATTERNS:
                if pattern.match(first_line):
                    if vertical_distance < best_distance:
                        best_distance = vertical_distance
                        # Clean up the caption: take the first line, merge line breaks
                        best_caption = re.sub(r"\n+", " ", block_text).strip()
                        # Limit caption length for filename use
                        if len(best_caption) > 120:
                            best_caption = best_caption[:120]
                    break

        return best_caption

    def _generate_image_name(
        self,
        page_num: int,
        img_index: int,
        xref_name: str = "",
        caption: Optional[str] = None,
        nearby_text: str = "",
        pdf_name: str = "",
    ) -> str:
        """Generate a meaningful filename for an extracted image.

        Priority:
        1. Caption text (e.g., "Figure 1: Architecture Diagram")
        2. PDF internal name from xref metadata
        3. Nearby text context
        4. Fallback: pdf_name + page + index
        """
        # 1. Try caption
        if caption:
            slug = self._slugify(caption)
            if slug and len(slug) >= 3:
                return slug

        # 2. Try PDF internal image name
        if xref_name and xref_name not in ("Im", "Image", "X", "img"):
            slug = self._slugify(xref_name)
            if slug and len(slug) >= 2:
                return f"p{page_num + 1}-{slug}"

        # 3. Try nearby text context (first 5 words)
        if nearby_text:
            words = nearby_text.split()[:5]
            context = " ".join(words)
            slug = self._slugify(context)
            if slug and len(slug) >= 3:
                return f"p{page_num + 1}-{slug}"

        # 4. Fallback
        base = self._slugify(pdf_name) if pdf_name else "img"
        if not base:
            base = "img"
        return f"{base}-p{page_num + 1}-{img_index + 1}"

    async def extract_images_from_pdf_page(
        self, pdf_document, page_num: int, image_format: str = "png"
    ) -> List[ExtractedImage]:
        """
        Extract images from a PDF page.

        Args:
            pdf_document: PyMuPDF document object
            page_num: Page number (0-indexed)
            image_format: Output image format (png, jpg, etc.)

        Returns:
            List of ExtractedImage objects
        """
        images = []

        try:
            # Check if PyMuPDF is available
            if fitz is None:
                raise ImportError("PyMuPDF (fitz) is not available")

            page = pdf_document[page_num]
            image_list = page.get_images(full=True)

            for img_index, img_info in enumerate(image_list):
                try:
                    xref = img_info[0]
                    pix = fitz.Pixmap(pdf_document, xref)

                    # Convert CMYK to RGB instead of skipping
                    if pix.n - pix.alpha >= 4:
                        pix = fitz.Pixmap(fitz.csRGB, pix)

                    # Generate image ID and filename
                    img_id = self._generate_asset_id("img", page_num, img_index)
                    filename = f"{img_id}.{image_format}"
                    local_path = self.output_dir / filename

                    # Save image to local file
                    if image_format.lower() == "png":
                        pix.save(str(local_path))
                    else:
                        with open(local_path, "wb") as f:
                            f.write(pix.tobytes(image_format.upper()))

                    # Get image dimensions
                    width, height = pix.width, pix.height

                    # Get base64 data for embedding
                    b64_data = base64.b64encode(
                        pix.tobytes(image_format.upper())
                    ).decode("ascii")

                    # Get real position using get_image_rects
                    position = None
                    try:
                        rects = page.get_image_rects(xref)
                        if rects:
                            rect = rects[0]
                            position = {
                                "x0": rect.x0,
                                "y0": rect.y0,
                                "x1": rect.x1,
                                "y1": rect.y1,
                            }
                    except Exception:
                        pass  # nosec B110

                    # Create ExtractedImage object
                    extracted_image = ExtractedImage(
                        id=img_id,
                        filename=filename,
                        local_path=str(local_path),
                        base64_data=b64_data,
                        mime_type=f"image/{image_format}",
                        width=width,
                        height=height,
                        page_number=page_num,
                        position=position,
                        xref=xref,
                    )

                    images.append(extracted_image)
                    self.logger.info(f"Extracted image {img_id} from page {page_num}")

                    pix = None  # Free memory

                except Exception as e:
                    self.logger.warning(
                        f"Failed to extract image {img_index} from page {page_num}: {str(e)}"
                    )
                    continue

        except ImportError:
            self.logger.error("PyMuPDF (fitz) is required for image extraction")
        except Exception as e:
            self.logger.error(f"Error extracting images from page {page_num}: {str(e)}")

        return images

    async def extract_images_with_positions(
        self,
        pdf_document,
        page_num: int,
        text_blocks: list,
        image_format: str = "png",
        pdf_name: str = "",
    ) -> Dict[int, ExtractedImage]:
        """Extract images and build block_no -> ExtractedImage mapping.

        This method correlates image xrefs with their visual block positions
        on the page so that images can be inlined at the correct text position.

        Args:
            pdf_document: PyMuPDF document object
            page_num: Page number (0-indexed)
            text_blocks: All blocks from page.get_text("blocks")
            image_format: Output image format
            pdf_name: Original PDF filename (for naming)

        Returns:
            Dict mapping block_no (int) to ExtractedImage
        """
        block_to_image: Dict[int, ExtractedImage] = {}

        try:
            if fitz is None:
                raise ImportError("PyMuPDF (fitz) is not available")

            page = pdf_document[page_num]
            image_list = page.get_images(full=True)

            if not image_list:
                return block_to_image

            # Build xref -> rect mapping
            xref_rects: Dict[int, Any] = {}
            for img_info in image_list:
                xref = img_info[0]
                try:
                    rects = page.get_image_rects(xref)
                    if rects:
                        xref_rects[xref] = rects[0]
                except Exception:
                    continue  # nosec B112

            # Collect image blocks (block[6] == 1)
            image_blocks = [b for b in text_blocks if b[6] == 1]
            # Collect text-only blocks for caption detection
            text_only_blocks = [b for b in text_blocks if b[6] == 0]

            # For each image block, find the best matching xref
            matched_xrefs: set = set()
            for block in image_blocks:
                b_x0, b_y0, b_x1, b_y1 = block[0], block[1], block[2], block[3]
                block_no = block[5]
                b_cx = (b_x0 + b_x1) / 2
                b_cy = (b_y0 + b_y1) / 2

                best_xref = None
                best_overlap = -1

                for xref, rect in xref_rects.items():
                    if xref in matched_xrefs:
                        continue
                    # Calculate IoU-like overlap
                    overlap_x0 = max(b_x0, rect.x0)
                    overlap_y0 = max(b_y0, rect.y0)
                    overlap_x1 = min(b_x1, rect.x1)
                    overlap_y1 = min(b_y1, rect.y1)

                    if overlap_x1 > overlap_x0 and overlap_y1 > overlap_y0:
                        overlap_area = (overlap_x1 - overlap_x0) * (
                            overlap_y1 - overlap_y0
                        )
                        if overlap_area > best_overlap:
                            best_overlap = overlap_area
                            best_xref = xref
                    else:
                        # Fallback: check if center of block is inside rect (with tolerance)
                        margin = 20
                        if (
                            rect.x0 - margin <= b_cx <= rect.x1 + margin
                            and rect.y0 - margin <= b_cy <= rect.y1 + margin
                        ):
                            # Use a small pseudo-overlap so actual overlaps take priority
                            if best_overlap < 0:
                                best_xref = xref

                if best_xref is None:
                    continue

                matched_xrefs.add(best_xref)

                # Find img_info for this xref
                img_info = None
                img_index = 0
                for idx, info in enumerate(image_list):
                    if info[0] == best_xref:
                        img_info = info
                        img_index = idx
                        break

                if img_info is None:
                    continue

                try:
                    pix = fitz.Pixmap(pdf_document, best_xref)

                    # Convert CMYK to RGB
                    if pix.n - pix.alpha >= 4:
                        pix = fitz.Pixmap(fitz.csRGB, pix)

                    width, height = pix.width, pix.height

                    # Detect caption from nearby text
                    rect = xref_rects[best_xref]
                    caption = self._detect_caption(
                        text_only_blocks, rect.y1, rect.x0, rect.x1
                    )

                    # Get xref internal name
                    xref_name = img_info[7] if len(img_info) > 7 else ""

                    # Find nearest text block for context (before the image)
                    nearby_text = ""
                    for tb in sorted(text_only_blocks, key=lambda b: b[1]):
                        if tb[1] < b_y0 and tb[4]:
                            nearby_text = tb[4].strip()

                    # Generate semantic name
                    name_slug = self._generate_image_name(
                        page_num, img_index, xref_name, caption, nearby_text, pdf_name
                    )
                    filename = f"{name_slug}.{image_format}"

                    # Avoid filename collisions
                    local_path = self.output_dir / filename
                    counter = 1
                    while local_path.exists():
                        filename = f"{name_slug}-{counter}.{image_format}"
                        local_path = self.output_dir / filename
                        counter += 1

                    # Save image
                    if image_format.lower() == "png":
                        pix.save(str(local_path))
                    else:
                        with open(local_path, "wb") as f:
                            f.write(pix.tobytes(image_format.upper()))

                    b64_data = base64.b64encode(
                        pix.tobytes(image_format.upper())
                    ).decode("ascii")

                    extracted_image = ExtractedImage(
                        id=f"img_{page_num}_{img_index}",
                        filename=filename,
                        local_path=str(local_path),
                        base64_data=b64_data,
                        mime_type=f"image/{image_format}",
                        width=width,
                        height=height,
                        page_number=page_num,
                        position={
                            "x0": rect.x0,
                            "y0": rect.y0,
                            "x1": rect.x1,
                            "y1": rect.y1,
                        },
                        caption=caption,
                        xref=best_xref,
                    )

                    block_to_image[block_no] = extracted_image
                    self.images.append(extracted_image)
                    self.logger.info(
                        f"Extracted image '{filename}' from page {page_num} (block {block_no})"
                    )

                    pix = None

                except Exception as e:
                    self.logger.warning(
                        f"Failed to extract image for block {block_no} on page {page_num}: {str(e)}"
                    )
                    continue

            # Handle xrefs that weren't matched to any block (rare edge case)
            for img_index, img_info in enumerate(image_list):
                xref = img_info[0]
                if xref in matched_xrefs:
                    continue

                try:
                    pix = fitz.Pixmap(pdf_document, xref)
                    if pix.n - pix.alpha >= 4:
                        pix = fitz.Pixmap(fitz.csRGB, pix)

                    width, height = pix.width, pix.height
                    xref_name = img_info[7] if len(img_info) > 7 else ""

                    # Get position if available
                    position = None
                    if xref in xref_rects:
                        rect = xref_rects[xref]
                        position = {
                            "x0": rect.x0,
                            "y0": rect.y0,
                            "x1": rect.x1,
                            "y1": rect.y1,
                        }

                    name_slug = self._generate_image_name(
                        page_num, img_index, xref_name, None, "", pdf_name
                    )
                    filename = f"{name_slug}.{image_format}"
                    local_path = self.output_dir / filename
                    counter = 1
                    while local_path.exists():
                        filename = f"{name_slug}-{counter}.{image_format}"
                        local_path = self.output_dir / filename
                        counter += 1

                    if image_format.lower() == "png":
                        pix.save(str(local_path))
                    else:
                        with open(local_path, "wb") as f:
                            f.write(pix.tobytes(image_format.upper()))

                    b64_data = base64.b64encode(
                        pix.tobytes(image_format.upper())
                    ).decode("ascii")

                    extracted_image = ExtractedImage(
                        id=f"img_{page_num}_{img_index}",
                        filename=filename,
                        local_path=str(local_path),
                        base64_data=b64_data,
                        mime_type=f"image/{image_format}",
                        width=width,
                        height=height,
                        page_number=page_num,
                        position=position,
                        xref=xref,
                    )
                    self.images.append(extracted_image)
                    self.logger.info(
                        f"Extracted unmatched image '{filename}' from page {page_num}"
                    )

                    pix = None

                except Exception as e:
                    self.logger.warning(
                        f"Failed to extract unmatched image xref={xref} on page {page_num}: {str(e)}"
                    )
                    continue

        except ImportError:
            self.logger.error("PyMuPDF (fitz) is required for image extraction")
        except Exception as e:
            self.logger.error(
                f"Error in extract_images_with_positions for page {page_num}: {str(e)}"
            )

        return block_to_image

    def _detect_table_caption(
        self,
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

    def extract_tables_with_geometry(
        self,
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
            title_regions = self._find_table_title_regions(
                page,
                text_only_blocks,
                page_rect,
            )

            if title_regions:
                # Extract each table using its clip region
                for table_idx, (title, clip_rect, title_rect) in enumerate(
                    title_regions
                ):
                    table = self._extract_single_table(
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
                found_tables = self._find_tables_fullpage(page)

                for table_idx, table in enumerate(found_tables):
                    extracted = self._process_found_table(
                        table,
                        text_only_blocks,
                        page_num,
                        table_idx,
                    )
                    if extracted:
                        bbox_to_table[extracted.bbox] = extracted  # type: ignore[index]
                        all_tables.append(extracted)

        except ImportError:
            self.logger.error(
                "PyMuPDF (fitz) is required for geometric table extraction"
            )
        except Exception as e:
            self.logger.error(
                f"Error in geometric table extraction for page {page_num}: {e}"
            )

        return bbox_to_table, all_tables

    def _find_table_title_regions(
        self,
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
        self,
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
            merged_data = self._merge_table_columns_and_rows(extracted_data)
            if not merged_data or len(merged_data) < 2:
                return None

            # Build markdown from merged data
            markdown_str = self._build_markdown_from_data(merged_data)
            if not markdown_str:
                return None

            # Use the title region + table body as the overall bbox
            bbox = (
                clip_rect.x0,
                title_rect.y0,
                clip_rect.x1,
                min(float(table.bbox[3]) + 5, float(clip_rect.y1)),
            )

            table_id = self._generate_asset_id("table", page_num, table_idx)

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
            self.logger.warning(
                f"Failed to extract table '{title}' on page {page_num}: {e}"
            )
            return None

    def _find_tables_fullpage(self, page) -> list:
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
        self,
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
            merged_data = self._merge_table_columns_and_rows(extracted_data)
            if not merged_data or len(merged_data) < 2:
                return None

            markdown_str = self._build_markdown_from_data(merged_data)
            if not markdown_str:
                return None

            bbox = tuple(table.bbox)

            caption = self._detect_table_caption(text_blocks, bbox, tolerance=30.0)

            table_id = self._generate_asset_id("table", page_num, table_idx)

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
            self.logger.warning(
                f"Failed to process table {table_idx} on page {page_num}: {e}"
            )
            return None

    @staticmethod
    def _merge_table_columns_and_rows(
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

    @staticmethod
    def _build_markdown_from_data(data: List[List[str]]) -> str:
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

    def extract_tables_from_text(
        self, text: str, page_num: int
    ) -> List[ExtractedTable]:
        """
        Extract tables from plain text using pattern recognition.

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
                if self._is_table_row(line):
                    table_lines = []

                    # Collect consecutive table rows
                    while i < len(lines) and self._is_table_row(lines[i].strip()):
                        table_lines.append(lines[i].strip())
                        i += 1

                    # Convert to Markdown table
                    if len(table_lines) >= 2:  # At least header and one data row
                        table_id = self._generate_asset_id(
                            "table", page_num, len(tables)
                        )
                        markdown_table = self._convert_to_markdown_table(table_lines)

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
                                headers=self._extract_table_headers(table_lines[0])
                                if table_lines
                                else None,
                            )

                            tables.append(extracted_table)
                            self.logger.info(
                                f"Extracted table {table_id} from page {page_num}"
                            )

                i += 1

        except Exception as e:
            self.logger.error(f"Error extracting tables from page {page_num}: {str(e)}")

        return tables

    def extract_formulas_from_text(
        self, text: str, page_num: int
    ) -> List[ExtractedFormula]:
        """
        Extract mathematical formulas from text.

        支持两层检测：
        1. LaTeX 定界符匹配 (``$...$``, ``$$...$$``, ``\\[...\\]``, ``\\(...\\)``)
        2. Unicode 数学符号检测（当无 LaTeX 定界符时自动启用）

        Args:
            text: Text content from PDF page
            page_num: Page number

        Returns:
            List of ExtractedFormula objects
        """
        formulas = []

        try:
            # 延迟导入避免循环依赖
            from .math_formula import unicode_to_latex, has_math_unicode

            # Layer 1: LaTeX 定界符匹配
            patterns = [
                # Block formulas: \[ ... \] or $$ ... $$
                (r"\\\[\s*([^]]+?)\s*\\\]", "block"),
                (r"\$\$\s*([^$]+?)\s*\$\$", "block"),
                # Inline formulas: \( ... \) or $ ... $
                (r"\\\(\s*([^)]+?)\s*\\\)", "inline"),
                (r"(?<!\$)\$([^$]+?)\$(?!\$)", "inline"),
            ]

            formula_index = 0
            matched_ranges = set()  # 记录已匹配区间避免重复

            for pattern, formula_type in patterns:
                matches = re.finditer(pattern, text, re.MULTILINE | re.DOTALL)

                for match in matches:
                    formula_content = match.group(1).strip()

                    if (
                        formula_content and len(formula_content) > 1
                    ):  # Filter out empty matches
                        formula_id = self._generate_asset_id(
                            "formula", page_num, formula_index
                        )

                        extracted_formula = ExtractedFormula(
                            id=formula_id,
                            latex=formula_content,
                            formula_type=formula_type,
                            page_number=page_num,
                            position={
                                "start": match.start(),
                                "end": match.end(),
                            },
                        )

                        formulas.append(extracted_formula)
                        matched_ranges.add((match.start(), match.end()))
                        formula_index += 1

                        self.logger.info(
                            f"Extracted {formula_type} formula {formula_id} from page {page_num}"
                        )

            # Layer 2: Unicode 数学符号检测
            # 当 Layer 1 未检测到公式时，扫描文本中的 Unicode 数学符号
            if not formulas and has_math_unicode(text):
                # 按行扫描，检测含有数学符号的文本段
                for line in text.split("\n"):
                    line_stripped = line.strip()
                    if not line_stripped or not has_math_unicode(line_stripped):
                        continue

                    latex_converted = unicode_to_latex(line_stripped)
                    if latex_converted != line_stripped:
                        formula_id = self._generate_asset_id(
                            "formula", page_num, formula_index
                        )
                        extracted_formula = ExtractedFormula(
                            id=formula_id,
                            latex=latex_converted,
                            formula_type="inline",
                            page_number=page_num,
                            description="Unicode math symbols detected",
                        )
                        formulas.append(extracted_formula)
                        formula_index += 1

        except Exception as e:
            self.logger.error(
                f"Error extracting formulas from page {page_num}: {str(e)}"
            )

        return formulas

    def _is_table_row(self, line: str) -> bool:
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
        return self._has_multiple_space_separators(line_stripped)

    def _has_multiple_space_separators(self, line: str) -> bool:
        """Check if a line has multiple space separators (more than 2 spaces between words)."""
        return bool(re.search(r" {2,}", line)) and len(line.split()) >= 3

    def _convert_to_markdown_table(self, table_lines: List[str]) -> str:
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
            self.logger.error(f"Error converting table to Markdown: {str(e)}")
            return ""

    def _extract_table_headers(self, header_line: str) -> List[str]:
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

    def enhance_markdown_with_assets(
        self,
        original_markdown: str,
        embed_images: bool = False,
        image_size: Optional[Tuple[int, int]] = None,
    ) -> str:
        """
        Enhance Markdown content with extracted images, tables, and formulas.

        Images that were already placed inline (their filename appears in the markdown)
        are skipped. Only unplaced images are appended at the end as a fallback.

        Args:
            original_markdown: Original Markdown content (may already contain inline images)
            embed_images: Whether to embed images as base64
            image_size: Optional resize dimensions (width, height)

        Returns:
            Enhanced Markdown content
        """
        enhanced_content = original_markdown

        try:
            # Determine which images are already inline in the markdown
            unplaced_images = []
            for img in self.images:
                if img.filename in original_markdown:
                    continue
                unplaced_images.append(img)

            # Only add images section for unplaced images
            if unplaced_images:
                enhanced_content += "\n\n## Extracted Images\n\n"

                for img in unplaced_images:
                    if embed_images and img.base64_data:
                        enhanced_content += f"![{img.caption or img.filename}](data:{img.mime_type};base64,{img.base64_data})\n\n"
                    else:
                        enhanced_content += (
                            f"![{img.caption or img.filename}]({img.filename})\n\n"
                        )

                    # Add image metadata
                    if img.width and img.height:
                        enhanced_content += (
                            f"*Dimensions: {img.width}\u00d7{img.height}px*\n"
                        )
                    if img.page_number is not None:
                        enhanced_content += f"*Source: Page {img.page_number + 1}*\n"
                    enhanced_content += "\n"

            # Add tables section — skip tables already placed inline
            if self.tables:
                unplaced_tables = []
                for table in self.tables:
                    # Use first data row as fingerprint for dedup
                    first_row = (
                        table.markdown.split("\n")[0].strip() if table.markdown else ""
                    )
                    if first_row and first_row in enhanced_content:
                        continue
                    unplaced_tables.append(table)

                if unplaced_tables:
                    enhanced_content += "\n## Extracted Tables\n\n"

                    for table in unplaced_tables:
                        if table.caption:
                            enhanced_content += f"**{table.caption}**\n\n"

                        enhanced_content += table.markdown + "\n\n"

                        # Add table metadata
                        enhanced_content += f"*Table: {table.rows} rows \u00d7 {table.columns} columns*\n"
                        if table.page_number is not None:
                            enhanced_content += (
                                f"*Source: Page {table.page_number + 1}*\n"
                            )
                        enhanced_content += "\n"

            # Add formulas section if any formulas were extracted
            if self.formulas:
                enhanced_content += "\n## Mathematical Formulas\n\n"

                for formula in self.formulas:
                    if formula.formula_type == "block":
                        enhanced_content += f"\n$$\n{formula.latex}\n$$\n\n"
                    else:
                        enhanced_content += f"${formula.latex}$\n\n"

                    # Add formula metadata
                    if formula.description:
                        enhanced_content += f"*{formula.description}*\n"
                    if formula.page_number is not None:
                        enhanced_content += (
                            f"*Source: Page {formula.page_number + 1}*\n"
                        )
                    enhanced_content += "\n"

        except Exception as e:
            self.logger.error(f"Error enhancing Markdown with assets: {str(e)}")

        return enhanced_content

    def get_extraction_summary(self) -> Dict[str, Any]:
        """Get a summary of all extracted content."""
        return {
            "images": {
                "count": len(self.images),
                "files": [img.filename for img in self.images],
                "total_size_mb": sum(
                    os.path.getsize(img.local_path)
                    for img in self.images
                    if os.path.exists(img.local_path)
                )
                / (1024 * 1024),
            },
            "tables": {
                "count": len(self.tables),
                "total_rows": sum(table.rows for table in self.tables),
                "total_columns": sum(table.columns for table in self.tables),
            },
            "formulas": {
                "count": len(self.formulas),
                "inline_count": len(
                    [f for f in self.formulas if f.formula_type == "inline"]
                ),
                "block_count": len(
                    [f for f in self.formulas if f.formula_type == "block"]
                ),
            },
            "output_directory": str(self.output_dir),
        }

    def cleanup(self):
        """Clean up temporary files and reset processor state."""
        try:
            # Clear extracted content
            self.images.clear()
            self.tables.clear()
            self.formulas.clear()

            # Note: Don't delete output directory here as it might contain
            # files that the user wants to keep

        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")
