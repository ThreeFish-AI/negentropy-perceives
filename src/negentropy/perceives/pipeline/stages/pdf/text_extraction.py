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
from typing import Any, Dict, List, Optional

from ...base import Stage, StageResult
from ...models import (
    PreprocessingOutput,
    TextBlock,
    TextExtractionOutput,
)
from ...registry import register_tool
from .._base import PDFToolBase

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 工具适配器
# ---------------------------------------------------------------------------


@register_tool("text_extraction.pymupdf")
class FitzTextExtractor(PDFToolBase):
    """基于 PyMuPDF 的文本提取工具。"""

    tool_name = "pymupdf"

    def is_available(self) -> bool:
        try:
            from ....pdf._imports import import_fitz

            import_fitz()
            return True
        except ImportError:
            return False

    async def _run(
        self, input_data: PreprocessingOutput
    ) -> StageResult[TextExtractionOutput]:
        """使用 PyMuPDF 提取文本块。"""
        try:
            from ....pdf._imports import import_fitz

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

            return StageResult(
                success=True,
                output=output,
                engine_used=self.tool_name,
            )

        except Exception as e:
            logger.warning("PyMuPDF 文本提取失败: %s", e)
            return StageResult(success=False, error=f"PyMuPDF 文本提取失败: {e}")


@register_tool("text_extraction.docling")
class DoclingTextExtractor(PDFToolBase):
    """基于 Docling 的文本提取工具。"""

    tool_name = "docling"

    def is_available(self) -> bool:
        try:
            from ....pdf.engines.docling import DoclingEngine

            return DoclingEngine.is_available()
        except ImportError:
            return False

    async def _run(
        self, input_data: PreprocessingOutput
    ) -> StageResult[TextExtractionOutput]:
        """使用 Docling 提取文本。

        优先消费 ``DoclingConversionResult.text_blocks``（携带 0-based ``page_number``
        与 TopLeft bbox），从根本上解决 ``export_to_markdown()`` 聚合输出导致段落
        无法定位到源页面的问题。当 ``text_blocks`` 为空时，降级到旧的「按 ``\\n\\n``
        拆段、page_number 缺省」路径以保持向后兼容。
        """
        try:
            from ....core.cancellation import current_cancel_scope
            from ....infra import get_engine_pool

            _scope = current_cancel_scope()
            result = await get_engine_pool().run(
                "docling",
                kwargs={
                    "pdf_path": str(input_data.local_path),
                    "page_range": input_data.page_range,
                },
                init_kwargs={},
                deadline_monotonic=_scope.deadline_monotonic if _scope else None,
            )
            if result is None or not result.markdown:
                return StageResult(success=False, error="Docling 返回空结果")

            blocks: List[TextBlock]
            if getattr(result, "text_blocks", None):
                blocks = self._blocks_from_text_blocks(result.text_blocks)
            else:
                blocks = self._fallback_markdown_split(result.markdown)

            full_text = result.markdown
            word_count = len(full_text.split())

            output = TextExtractionOutput(
                blocks=blocks,
                full_text=full_text,
                word_count=word_count,
                metadata={"engine": "docling"},
            )

            return StageResult(
                success=True,
                output=output,
                engine_used=self.tool_name,
            )

        except Exception as e:
            logger.warning("Docling 文本提取失败: %s", e)
            return StageResult(success=False, error=f"Docling 文本提取失败: {e}")

    @staticmethod
    def _blocks_from_text_blocks(text_blocks: List[Any]) -> List[TextBlock]:
        """从 ``DoclingTextBlock`` 列表构造 ``TextBlock``，保留页码与 bbox。"""
        blocks: List[TextBlock] = []
        for ro, tb in enumerate(text_blocks):
            label = (tb.label or "paragraph").lower()
            if label in ("title", "section_header"):
                block_type = "heading"
                heading_level = tb.heading_level or (1 if label == "title" else 2)
            elif label == "list_item":
                block_type = "list_item"
                heading_level = None
            elif label == "footnote":
                block_type = "footnote"
                heading_level = None
            else:
                block_type = "paragraph"
                heading_level = None

            blocks.append(
                TextBlock(
                    text=tb.text,
                    page_number=tb.page_number if tb.page_number is not None else 0,
                    bbox=tb.bbox,
                    block_type=block_type,
                    heading_level=heading_level,
                    reading_order=ro,
                )
            )
        return blocks

    @staticmethod
    def _fallback_markdown_split(markdown: str) -> List[TextBlock]:
        """旧的兜底路径：按 ``\\n\\n`` 拆段、page_number=0。"""
        blocks: List[TextBlock] = []
        reading_order = 0
        for paragraph in markdown.split("\n\n"):
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            block_type = "paragraph"
            heading_level: Optional[int] = None

            heading_match = re.match(r"^(#{1,6})\s+(.+)", paragraph)
            if heading_match:
                block_type = "heading"
                heading_level = len(heading_match.group(1))
                paragraph = heading_match.group(2)

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
        return blocks


@register_tool("text_extraction.pypdf")
class PyPDFTextExtractor(PDFToolBase):
    """基于 pypdf 的文本提取工具（降级方案）。"""

    tool_name = "pypdf"

    def is_available(self) -> bool:
        try:
            from ....pdf._imports import import_pypdf

            import_pypdf()
            return True
        except ImportError:
            return False

    async def _run(
        self, input_data: PreprocessingOutput
    ) -> StageResult[TextExtractionOutput]:
        """使用 pypdf 提取文本。"""
        try:
            from ....pdf._imports import import_pypdf

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

            return StageResult(
                success=True,
                output=output,
                engine_used=self.tool_name,
            )

        except Exception as e:
            logger.warning("pypdf 文本提取失败: %s", e)
            return StageResult(success=False, error=f"pypdf 文本提取失败: {e}")


@register_tool("text_extraction.opendataloader")
class OpenDataLoaderTextExtractor(PDFToolBase):
    """基于 OpenDataLoader 的文本提取工具（Apache-2.0 / CPU-only / 全元素 bbox）。"""

    tool_name = "opendataloader"

    def is_available(self) -> bool:
        try:
            from ....pdf.engines.opendataloader import OpenDataLoaderEngine

            return OpenDataLoaderEngine.is_available()
        except ImportError:
            return False

    async def _run(
        self, input_data: PreprocessingOutput
    ) -> StageResult[TextExtractionOutput]:
        """使用 OpenDataLoader 提取文本。

        OpenDataLoader 返回的 ``EngineConversionResult.markdown`` 已包含全文，
        但不携带逐段页码/bbox 信息，降级为按 ``\\n\\n`` 拆段、page_number 缺省路径。
        """
        try:
            from ....core.cancellation import current_cancel_scope
            from ....infra import get_engine_pool

            _scope = current_cancel_scope()
            result = await get_engine_pool().run(
                "opendataloader",
                kwargs={"pdf_path": str(input_data.local_path)},
                init_kwargs={},
                deadline_monotonic=_scope.deadline_monotonic if _scope else None,
            )
            if result is None or not result.markdown:
                return StageResult(success=False, error="OpenDataLoader 返回空结果")

            blocks: List[TextBlock] = []
            full_text = result.markdown
            word_count = len(full_text.split())

            output = TextExtractionOutput(
                blocks=blocks,
                full_text=full_text,
                word_count=word_count,
                metadata={"engine": "opendataloader"},
            )

            return StageResult(
                success=True,
                output=output,
                engine_used=self.tool_name,
            )

        except Exception as e:
            logger.warning("OpenDataLoader 文本提取失败: %s", e)
            return StageResult(success=False, error=f"OpenDataLoader 文本提取失败: {e}")


# ---------------------------------------------------------------------------
# Stage 本地工具映射
# ---------------------------------------------------------------------------

_TOOLS: Dict[str, type] = {
    "pymupdf": FitzTextExtractor,
    "docling": DoclingTextExtractor,
    "pypdf": PyPDFTextExtractor,
    "opendataloader": OpenDataLoaderTextExtractor,
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
        return StageResult(success=False, error="无可用的文本提取工具")
