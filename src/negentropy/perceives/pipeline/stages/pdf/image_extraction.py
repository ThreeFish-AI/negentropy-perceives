"""S6: 图片提取 Stage。

图片提取、分类与 caption 生成。

委托关系：
- ``pdf.enhanced.EnhancedPDFProcessor.extract_images_with_positions()`` — PyMuPDF 图片提取

并发策略：PyMuPDF 的 ``fitz.Document`` 对象并非线程安全，跨 worker 共享会
触发 SIGSEGV 或数据损坏（参见 PyMuPDF FAQ "Is PyMuPDF thread-safe?"）。
因此每页独立调用 ``fitz.open()``（官方实测 <10ms 的轻量操作），再通过
``asyncio.gather + Semaphore`` 限制并发度，既规避线程安全问题，又避免
长 PDF 同时打开过多文件句柄。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, List

from ...base import Stage, StageResult
from ...models import (
    ExtractedImage,
    ImageExtractionOutput,
    PreprocessingOutput,
)
from ...registry import register_tool
from .._base import PDFToolBase

logger = logging.getLogger(__name__)

# 默认页级并发上限（与 Pool 的 docling/mineru 竞争线一致），保留为模块级常量
# 兼容历史导入；运行时由 ``_resolve_concurrency()`` 从 settings 读取覆盖值。
_IMAGE_EXTRACT_CONCURRENCY = 4


def _resolve_concurrency() -> int:
    """从配置读取页级并发上限，失败回退到 ``_IMAGE_EXTRACT_CONCURRENCY``。

    M 系列大内存机型可上调以减少 18 张图 91s 的单线性瓶颈；
    旧机型或 GPU 紧张场景可下调到 4 维持原行为。
    """
    try:
        from ....config import settings as _settings

        val = int(_settings.pdf_image_extraction_concurrency)
        return max(1, val)
    except Exception:  # noqa: BLE001 - 配置未就绪时不阻塞抽图
        return _IMAGE_EXTRACT_CONCURRENCY


# ---------------------------------------------------------------------------
# 工具适配器
# ---------------------------------------------------------------------------


@register_tool("image_extraction.pymupdf")
class FitzImageExtractor(PDFToolBase):
    """基于 PyMuPDF 的图片提取工具。

    委托给 ``EnhancedPDFProcessor.extract_images_from_pdf_page()``。
    """

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
    ) -> StageResult[ImageExtractionOutput]:
        """使用 PyMuPDF 提取图片（分页并发）。"""
        try:
            from ....pdf._imports import import_fitz
            from ....pdf.enhanced import EnhancedPDFProcessor

            fitz = import_fitz()
            pdf_path = str(input_data.local_path)

            # 先用一次性 Document 读取页数，随后立即关闭；实际抽取走分页
            # 并发路径，每页独立 open/close（PyMuPDF 线程不安全，详见文件
            # 头部注释）。
            with fitz.open(pdf_path) as probe_doc:
                total_pages = probe_doc.page_count

            start_page = 0
            end_page = total_pages
            if input_data.page_range:
                start_page = max(0, input_data.page_range[0])
                end_page = min(total_pages, input_data.page_range[1])

            concurrency = _resolve_concurrency()
            sem = asyncio.Semaphore(concurrency)

            async def _extract_one_page(
                page_idx: int,
            ) -> List[ExtractedImage]:
                """在独立 Document 上提取单页图片；受 Semaphore 限流。"""
                async with sem:
                    # 每个协程使用独立的 Document + processor，避免 fitz
                    # 对象被多协程交替访问（PyMuPDF 非线程/非重入安全）。
                    processor = EnhancedPDFProcessor()
                    doc = fitz.open(pdf_path)
                    try:
                        page_images = await processor.extract_images_from_pdf_page(
                            doc, page_idx
                        )
                    finally:
                        doc.close()
                    results: List[ExtractedImage] = []
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
                        results.append(
                            ExtractedImage(
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
                    # 按 bbox y0 排序分配 reading_order，使图片在页内有序
                    results.sort(key=lambda img: img.bbox[1] if img.bbox else 0)
                    for order, img in enumerate(results):
                        img.reading_order = order
                    return results

            if end_page <= start_page:
                pages_results: List[List[ExtractedImage]] = []
            else:
                pages_results = await asyncio.gather(
                    *(_extract_one_page(p) for p in range(start_page, end_page))
                )

            images: List[ExtractedImage] = [
                img for page_images in pages_results for img in page_images
            ]

            output = ImageExtractionOutput(
                images=images,
                total_count=len(images),
                metadata={
                    "engine": "pymupdf",
                    "concurrency": concurrency,
                    "page_count": max(0, end_page - start_page),
                },
            )

            return StageResult(
                success=True,
                output=output,
                engine_used=self.tool_name,
            )

        except Exception as e:
            logger.warning("PyMuPDF 图片提取失败: %s", e)
            return StageResult(success=False, error=f"PyMuPDF 图片提取失败: {e}")


# ---------------------------------------------------------------------------
# Stage 本地工具映射
# ---------------------------------------------------------------------------

_TOOLS: Dict[str, type] = {
    "pymupdf": FitzImageExtractor,
}


# ---------------------------------------------------------------------------
# Stage 类
# ---------------------------------------------------------------------------


class ImageExtractionStage(Stage[PreprocessingOutput, ImageExtractionOutput]):
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
