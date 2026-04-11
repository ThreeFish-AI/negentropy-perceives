"""S3: 文本内容提取 Stage。

从各文本区域中提取纯文本，保留段落结构与标题层级。

委托关系：
- ``pdf.processor.PDFProcessor._extract_with_pymupdf()`` — PyMuPDF 块级提取
- ``pdf.processor.PDFProcessor._extract_with_pypdf()`` — pypdf 基础提取
- ``pdf.docling_engine.DoclingEngine`` — Docling 全文 Markdown
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional

from ..base import Stage, StageResult, StageTool
from ..models import (
    PreprocessingOutput,
    TextBlock,
    TextExtractionOutput,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 工具适配器
# ---------------------------------------------------------------------------


class PyMuPDFTextExtractor:
    """基于 PyMuPDF 的文本提取工具。"""

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
    ) -> StageResult[TextExtractionOutput]:
        """使用 PyMuPDF 提取文本块。"""
        start = time.monotonic()
        try:
            from ...pdf._imports import import_fitz

            fitz = import_fitz()

            doc = fitz.open(str(input_data.local_path))
            start_page = 0
            end_page = doc.page_count
            if input_data.page_range:
                start_page = max(0, input_data.page_range[0])
                end_page = min(doc.page_count, input_data.page_range[1])

            blocks: List[TextBlock] = []
            full_text_parts: List[str] = []
            reading_order = 0

            for page_idx in range(start_page, end_page):
                page = doc[page_idx]
                raw_blocks = page.get_text("blocks")

                for block in sorted(raw_blocks, key=lambda b: (b[1], b[0])):
                    if block[6] != 0:  # 跳过非文本块
                        continue
                    text = block[4].strip()
                    if not text:
                        continue

                    bbox = (
                        float(block[0]),
                        float(block[1]),
                        float(block[2]),
                        float(block[3]),
                    )

                    # 启发式标题检测：使用字体大小
                    block_type = "paragraph"
                    heading_level: Optional[int] = None

                    # 合并块内换行
                    text = re.sub(r"\n+", " ", text)

                    text_block = TextBlock(
                        text=text,
                        page_number=page_idx,
                        bbox=bbox,
                        block_type=block_type,
                        heading_level=heading_level,
                        reading_order=reading_order,
                    )
                    blocks.append(text_block)
                    full_text_parts.append(text)
                    reading_order += 1

            doc.close()

            full_text = "\n\n".join(full_text_parts)
            word_count = len(full_text.split())

            output = TextExtractionOutput(
                blocks=blocks,
                full_text=full_text,
                word_count=word_count,
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
            logger.warning("PyMuPDF 文本提取失败: %s", e)
            return StageResult(
                success=False, error=f"PyMuPDF 文本提取失败: {e}"
            )


class DoclingTextExtractor:
    """基于 Docling 的文本提取工具。"""

    @property
    def name(self) -> str:
        return "docling"

    def is_available(self) -> bool:
        try:
            from ...pdf.docling_engine import DoclingEngine

            return DoclingEngine.is_available()
        except ImportError:
            return False

    async def execute(
        self, input_data: PreprocessingOutput
    ) -> StageResult[TextExtractionOutput]:
        """使用 Docling 提取文本。"""
        start = time.monotonic()
        try:
            from ...pdf.docling_engine import DoclingEngine

            engine = DoclingEngine()
            result = engine.convert(
                str(input_data.local_path),
                page_range=input_data.page_range,
            )
            if result is None or not result.markdown:
                return StageResult(
                    success=False, error="Docling 返回空结果"
                )

            # 将 Markdown 内容解析为 TextBlock 列表
            blocks: List[TextBlock] = []
            reading_order = 0
            for paragraph in result.markdown.split("\n\n"):
                paragraph = paragraph.strip()
                if not paragraph:
                    continue

                block_type = "paragraph"
                heading_level: Optional[int] = None

                # 检测标题
                heading_match = re.match(r"^(#{1,6})\s+(.+)", paragraph)
                if heading_match:
                    block_type = "heading"
                    heading_level = len(heading_match.group(1))
                    paragraph = heading_match.group(2)

                # 检测列表
                if re.match(r"^\s*[-*+]\s", paragraph) or re.match(
                    r"^\s*\d+\.\s", paragraph
                ):
                    block_type = "list_item"

                blocks.append(
                    TextBlock(
                        text=paragraph,
                        page_number=0,
                        block_type=block_type,
                        heading_level=heading_level,
                        reading_order=reading_order,
                    )
                )
                reading_order += 1

            full_text = result.markdown
            word_count = len(full_text.split())

            output = TextExtractionOutput(
                blocks=blocks,
                full_text=full_text,
                word_count=word_count,
                metadata={"engine": "docling"},
            )

            elapsed = (time.monotonic() - start) * 1000
            return StageResult(
                success=True,
                output=output,
                engine_used="docling",
                elapsed_ms=elapsed,
            )

        except Exception as e:
            logger.warning("Docling 文本提取失败: %s", e)
            return StageResult(
                success=False, error=f"Docling 文本提取失败: {e}"
            )


class PyPDFTextExtractor:
    """基于 pypdf 的文本提取工具（降级方案）。"""

    @property
    def name(self) -> str:
        return "pypdf"

    def is_available(self) -> bool:
        try:
            from ...pdf._imports import import_pypdf

            import_pypdf()
            return True
        except ImportError:
            return False

    async def execute(
        self, input_data: PreprocessingOutput
    ) -> StageResult[TextExtractionOutput]:
        """使用 pypdf 提取文本。"""
        start = time.monotonic()
        try:
            from ...pdf._imports import import_pypdf

            pypdf = import_pypdf()

            reader = pypdf.PdfReader(str(input_data.local_path))
            start_page = 0
            end_page = len(reader.pages)
            if input_data.page_range:
                start_page = max(0, input_data.page_range[0])
                end_page = min(len(reader.pages), input_data.page_range[1])

            blocks: List[TextBlock] = []
            full_text_parts: List[str] = []
            reading_order = 0

            for page_idx in range(start_page, end_page):
                text = reader.pages[page_idx].extract_text() or ""
                text = text.strip()
                if not text:
                    continue

                blocks.append(
                    TextBlock(
                        text=text,
                        page_number=page_idx,
                        block_type="paragraph",
                        reading_order=reading_order,
                    )
                )
                full_text_parts.append(text)
                reading_order += 1

            full_text = "\n\n".join(full_text_parts)
            word_count = len(full_text.split())

            output = TextExtractionOutput(
                blocks=blocks,
                full_text=full_text,
                word_count=word_count,
                metadata={"engine": "pypdf"},
            )

            elapsed = (time.monotonic() - start) * 1000
            return StageResult(
                success=True,
                output=output,
                engine_used="pypdf",
                elapsed_ms=elapsed,
            )

        except Exception as e:
            logger.warning("pypdf 文本提取失败: %s", e)
            return StageResult(
                success=False, error=f"pypdf 文本提取失败: {e}"
            )


# ---------------------------------------------------------------------------
# Stage 本地工具映射
# ---------------------------------------------------------------------------

_TOOLS: Dict[str, type] = {
    "pymupdf": PyMuPDFTextExtractor,
    "docling": DoclingTextExtractor,
    "pypdf": PyPDFTextExtractor,
}


# ---------------------------------------------------------------------------
# Stage 类
# ---------------------------------------------------------------------------


class TextExtractionStage(Stage[PreprocessingOutput, TextExtractionOutput]):
    """S3: 文本内容提取 Stage。"""

    STAGE_ID = "text_extraction"
    STAGE_NAME = "文本内容提取"
    TOOLS = _TOOLS

    @property
    def stage_id(self) -> str:
        return self.STAGE_ID

    @property
    def stage_name(self) -> str:
        return self.STAGE_NAME

    async def execute(
        self, input_data: PreprocessingOutput
    ) -> StageResult[TextExtractionOutput]:
        """按降级顺序执行文本提取。"""
        for tool_cls in _TOOLS.values():
            tool = tool_cls()
            if tool.is_available():
                result = await tool.execute(input_data)
                if result.success:
                    return result
        return StageResult(
            success=False, error="无可用的文本提取工具"
        )
