"""S7: 代码块检测 Stage。

代码块与算法/伪代码检测，支持多引擎竞争。

委托关系：
- ``pdf.docling_engine.DoclingEngine`` — Docling CodeFormula 代码块提取
- ``pdf.marker_engine.MarkerEngine`` — Marker 代码块提取
- ``markdown.algorithm_detector`` — 启发式算法/伪代码检测
"""

from __future__ import annotations

import logging
from typing import Dict, List

from ...base import Stage, StageResult
from ...models import (
    CodeDetectionOutput,
    ExtractedCodeBlock,
    PreprocessingOutput,
)
from .._base import PDFToolBase

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 工具适配器
# ---------------------------------------------------------------------------


class DoclingCodeDetector(PDFToolBase):
    """基于 Docling 的代码块检测工具。"""

    tool_name = "docling"

    def is_available(self) -> bool:
        try:
            from ....pdf.engines.docling import DoclingEngine

            return DoclingEngine.is_available()
        except ImportError:
            return False

    async def _run(
        self, input_data: PreprocessingOutput
    ) -> StageResult[CodeDetectionOutput]:
        """使用 Docling 检测代码块。"""
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
            if result is None:
                return StageResult(success=False, error="Docling 转换返回空结果")

            code_blocks: List[ExtractedCodeBlock] = []
            for idx, cb in enumerate(result.code_blocks):
                code_blocks.append(
                    ExtractedCodeBlock(
                        code_id=f"code_{idx}",
                        code=cb.code,
                        language=cb.language,
                        page_number=cb.page_number or 0,
                        confidence=0.9,
                    )
                )

            output = CodeDetectionOutput(
                code_blocks=code_blocks,
                total_count=len(code_blocks),
                metadata={"engine": "docling"},
            )

            return StageResult(
                success=True,
                output=output,
                engine_used=self.tool_name,
            )

        except Exception as e:
            logger.warning("Docling 代码块检测失败: %s", e)
            return StageResult(success=False, error=f"Docling 代码块检测失败: {e}")


class MarkerCodeDetector(PDFToolBase):
    """基于 Marker 的代码块检测工具。"""

    tool_name = "marker"

    def is_available(self) -> bool:
        try:
            from ....pdf.engines.marker import MarkerEngine

            return MarkerEngine.is_available()
        except ImportError:
            return False

    async def _run(
        self, input_data: PreprocessingOutput
    ) -> StageResult[CodeDetectionOutput]:
        """使用 Marker 检测代码块。"""
        try:
            from ....core.cancellation import current_cancel_scope
            from ....infra import get_engine_pool

            _scope = current_cancel_scope()
            result = await get_engine_pool().run(
                "marker",
                kwargs={"pdf_path": str(input_data.local_path)},
                init_kwargs={},
                deadline_monotonic=_scope.deadline_monotonic if _scope else None,
            )
            if result is None:
                return StageResult(success=False, error="Marker 转换返回空结果")

            code_blocks: List[ExtractedCodeBlock] = []
            for idx, cb in enumerate(result.code_blocks):
                code_blocks.append(
                    ExtractedCodeBlock(
                        code_id=f"code_{idx}",
                        code=cb.code,
                        language=cb.language,
                        page_number=cb.page_number or 0,
                        confidence=0.85,
                    )
                )

            output = CodeDetectionOutput(
                code_blocks=code_blocks,
                total_count=len(code_blocks),
                metadata={"engine": "marker"},
            )

            return StageResult(
                success=True,
                output=output,
                engine_used=self.tool_name,
            )

        except Exception as e:
            logger.warning("Marker 代码块检测失败: %s", e)
            return StageResult(success=False, error=f"Marker 代码块检测失败: {e}")


class AlgorithmCodeDetector(PDFToolBase):
    """基于启发式评分的算法/伪代码检测工具。

    委托给 ``markdown.algorithm_detector.detect_algorithm_regions()``，
    在已提取的文本中扫描算法伪代码区域。
    """

    tool_name = "algorithm_detector"

    def is_available(self) -> bool:
        try:
            from ....markdown.algorithm_detector import detect_algorithm_regions  # noqa: F401

            return True
        except ImportError:
            return False

    async def _run(
        self, input_data: PreprocessingOutput
    ) -> StageResult[CodeDetectionOutput]:
        """使用启发式评分检测算法/伪代码块。

        从 PDF 中提取全文，然后用 ``detect_algorithm_regions()`` 扫描。
        """
        try:
            from ....markdown.algorithm_detector import (
                detect_algorithm_regions,
            )
            from ....pdf._imports import import_fitz

            fitz = import_fitz()

            doc = fitz.open(str(input_data.local_path))
            start_page = 0
            end_page = doc.page_count
            if input_data.page_range:
                start_page = max(0, input_data.page_range[0])
                end_page = min(doc.page_count, input_data.page_range[1])

            # 逐页提取文本，用双换行拼接
            page_texts: List[str] = []
            for page_idx in range(start_page, end_page):
                page = doc[page_idx]
                page_text = page.get_text("text")
                if page_text.strip():
                    page_texts.append(page_text)

            doc.close()

            full_text = "\n\n".join(page_texts)
            regions = detect_algorithm_regions(full_text)

            code_blocks: List[ExtractedCodeBlock] = []
            for idx, region in enumerate(regions):
                code_blocks.append(
                    ExtractedCodeBlock(
                        code_id=f"algo_{idx}",
                        code=region.content,
                        language="algorithm",
                        is_algorithm=True,
                        confidence=region.confidence,
                    )
                )

            output = CodeDetectionOutput(
                code_blocks=code_blocks,
                total_count=len(code_blocks),
                metadata={
                    "engine": "algorithm_detector",
                    "detection_threshold": "heuristic",
                },
            )

            return StageResult(
                success=True,
                output=output,
                engine_used=self.tool_name,
            )

        except Exception as e:
            logger.warning("算法检测器执行失败: %s", e)
            return StageResult(success=False, error=f"算法检测器执行失败: {e}")


# ---------------------------------------------------------------------------
# Stage 本地工具映射
# ---------------------------------------------------------------------------

_TOOLS: Dict[str, type] = {
    "docling": DoclingCodeDetector,
    "marker": MarkerCodeDetector,
    "algorithm_detector": AlgorithmCodeDetector,
}


# ---------------------------------------------------------------------------
# Stage 类
# ---------------------------------------------------------------------------


class CodeDetectionStage(Stage[PreprocessingOutput, CodeDetectionOutput]):
    """S7: 代码块检测 Stage。"""

    STAGE_ID = "code_detection"
    STAGE_NAME = "代码块与算法检测"
    TOOLS = _TOOLS

    @property
    def stage_id(self) -> str:
        return self.STAGE_ID

    @property
    def stage_name(self) -> str:
        return self.STAGE_NAME

    async def execute(
        self, input_data: PreprocessingOutput
    ) -> StageResult[CodeDetectionOutput]:
        """按降级顺序执行代码块检测。"""
        for tool_cls in _TOOLS.values():
            tool = tool_cls()
            if tool.is_available():
                result = await tool.execute(input_data)
                if result.success:
                    return result
        return StageResult(success=False, error="无可用的代码块检测工具")
