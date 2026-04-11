"""S6: 图片提取 Stage。

图片提取、分类与 caption 生成。

委托关系：
- ``pdf.enhanced.EnhancedPDFProcessor.extract_images_with_positions()`` — PyMuPDF 图片提取
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List

from ..base import Stage, StageResult
from ..models import (
    ExtractedImageV2,
    ImageExtractionOutput,
    PreprocessingOutput,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 工具适配器
# ---------------------------------------------------------------------------


class PyMuPDFImageExtractor:
    """基于 PyMuPDF 的图片提取工具。

    委托给 ``EnhancedPDFProcessor.extract_images_from_pdf_page()``。
    """

    @property
    def name(self) -> str:
        return "pymupdf"

    def is_available(self) -> bool:
        try:
            from ...pdf._imports import import_fitz

            import_fitz()
            return True
        except ImportError:
            return False

    async def execute(
        self, input_data: PreprocessingOutput
    ) -> StageResult[ImageExtractionOutput]:
        """使用 PyMuPDF 提取图片。"""
        start = time.monotonic()
        try:
            from ...pdf._imports import import_fitz
            from ...pdf.enhanced import EnhancedPDFProcessor

            fitz = import_fitz()
            processor = EnhancedPDFProcessor()

            doc = fitz.open(str(input_data.local_path))
            start_page = 0
            end_page = doc.page_count
            if input_data.page_range:
                start_page = max(0, input_data.page_range[0])
                end_page = min(doc.page_count, input_data.page_range[1])

            images: List[ExtractedImageV2] = []
            img_idx = 0

            for page_idx in range(start_page, end_page):
                page_images = await processor.extract_images_from_pdf_page(
                    doc, page_idx
                )
                for extracted_img in page_images:
                    bbox = None
                    if extracted_img.position:
                        pos = extracted_img.position
                        bbox = (
                            pos.get("x0", 0),
                            pos.get("y0", 0),
                            pos.get("x1", 0),
                            pos.get("y1", 0),
                        )

                    images.append(
                        ExtractedImageV2(
                            image_id=extracted_img.id,
                            filename=extracted_img.filename,
                            local_path=extracted_img.local_path,
                            base64_data=extracted_img.base64_data,
                            mime_type=extracted_img.mime_type,
                            width=extracted_img.width,
                            height=extracted_img.height,
                            page_number=page_idx,
                            bbox=bbox,
                            caption=extracted_img.caption,
                        )
                    )
                    img_idx += 1

            doc.close()

            output = ImageExtractionOutput(
                images=images,
                total_count=len(images),
                metadata={"engine": "pymupdf"},
            )

            elapsed = (time.monotonic() - start) * 1000
            return StageResult(
                success=True,
                output=output,
                engine_used="pymupdf",
                elapsed_ms=elapsed,
            )

        except Exception as e:
            logger.warning("PyMuPDF 图片提取失败: %s", e)
            return StageResult(
                success=False, error=f"PyMuPDF 图片提取失败: {e}"
            )


# ---------------------------------------------------------------------------
# Stage 本地工具映射
# ---------------------------------------------------------------------------

_TOOLS: Dict[str, type] = {
    "pymupdf": PyMuPDFImageExtractor,
}


# ---------------------------------------------------------------------------
# Stage 类
# ---------------------------------------------------------------------------


class ImageExtractionStage(
    Stage[PreprocessingOutput, ImageExtractionOutput]
):
    """S6: 图片提取 Stage。"""

    STAGE_ID = "image_extraction"
    STAGE_NAME = "图片提取"
    TOOLS = _TOOLS

    @property
    def stage_id(self) -> str:
        return self.STAGE_ID

    @property
    def stage_name(self) -> str:
        return self.STAGE_NAME

    async def execute(
        self, input_data: PreprocessingOutput
    ) -> StageResult[ImageExtractionOutput]:
        """执行图片提取。"""
        for tool_cls in _TOOLS.values():
            tool = tool_cls()
            if tool.is_available():
                return await tool.execute(input_data)
        return StageResult(
            success=False, error="无可用的图片提取工具（pymupdf 未安装）"
        )
